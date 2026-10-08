/** A failed API request, with the explanation the server gave when there was one. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string
  ) {
    super(detail || `Request failed (${status})`);
  }
}

async function errorFrom(response: Response): Promise<ApiError> {
  let detail = '';
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') detail = body.detail;
  } catch {
    // The body was not JSON; the status code alone will have to do.
  }
  return new ApiError(response.status, detail);
}

export async function getJson(url: string): Promise<unknown> {
  const response = await globalThis.fetch(url);
  if (!response.ok) throw await errorFrom(response);
  return (await response.json()) as unknown;
}

/** POSTs JSON and hands the plain-text response to `onText` as it arrives. */
export async function postStream(
  url: string,
  body: unknown,
  onText: (text: string) => void
): Promise<void> {
  const response = await globalThis.fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body)
  });
  if (!response.ok) throw await errorFrom(response);

  if (!response.body) {
    onText(await response.text());
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    onText(decoder.decode(value, { stream: true }));
  }
  const rest = decoder.decode();
  if (rest) onText(rest);
}
