import type { Card, Column } from '$lib/board';

type ApiBoard = {
  id: string;
  name: string;
  columns: Array<Column & { position: number }>;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await globalThis.fetch(path, {
    ...init,
    credentials: 'same-origin',
    headers: { 'content-type': 'application/json', ...init?.headers }
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(body?.detail ?? 'The board request failed', response.status);
  }
  return (await response.json()) as T;
}

export function getBoard(): Promise<ApiBoard> {
  return request<ApiBoard>('/api/board');
}

export function renameColumn(columnId: string, name: string): Promise<ApiBoard> {
  return request<ApiBoard>(`/api/board/columns/${columnId}`, {
    method: 'PATCH',
    body: JSON.stringify({ name })
  });
}

export function addCard(columnId: string, title: string, details: string): Promise<ApiBoard> {
  return request<ApiBoard>('/api/board/cards', {
    method: 'POST',
    body: JSON.stringify({ column_id: columnId, title, details })
  });
}

export function updateCard(cardId: string, title: string, details: string): Promise<ApiBoard> {
  return request<ApiBoard>(`/api/board/cards/${cardId}`, {
    method: 'PATCH',
    body: JSON.stringify({ title, details })
  });
}

export function removeCard(cardId: string): Promise<ApiBoard> {
  return request<ApiBoard>(`/api/board/cards/${cardId}`, { method: 'DELETE' });
}

export function moveCard(cardId: string, columnId: string): Promise<ApiBoard> {
  return request<ApiBoard>(`/api/board/cards/${cardId}/move`, {
    method: 'POST',
    body: JSON.stringify({ column_id: columnId })
  });
}

export function toColumns(board: ApiBoard): Column[] {
  return board.columns.map((column) => ({
    id: column.id,
    name: column.name,
    cards: column.cards.map((card: Card) => ({
      id: card.id,
      title: card.title,
      details: card.details
    }))
  }));
}
