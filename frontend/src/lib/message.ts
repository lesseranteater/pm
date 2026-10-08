export async function getMessage(): Promise<string> {
  const response = await globalThis.fetch('/api/message');
  if (!response.ok) throw new Error('Message request failed');

  const body = (await response.json()) as { message?: unknown };
  if (typeof body.message !== 'string') throw new Error('Message response is invalid');
  return body.message;
}
