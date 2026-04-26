import type { N8nPayload } from './types';

const BASE = import.meta.env.VITE_API_URL ?? '';

export async function sendToN8n(payload: N8nPayload): Promise<Response> {
  console.log('[ConsultantIQ] Triggering via backend:', payload);

  const response = await fetch(`${BASE}/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chatInput: payload.chatInput,
      sessionId: payload.sessionId,
    }),
  });

  return response;
}
