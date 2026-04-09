import type { N8nPayload } from './types';

const N8N_WEBHOOK_URL = import.meta.env.VITE_N8N_WEBHOOK_URL || '';

export async function sendToN8n(payload: N8nPayload): Promise<Response> {
  console.log('[ConsultantIQ] Webhook URL:', N8N_WEBHOOK_URL);
  console.log('[ConsultantIQ] Sending:', payload);

  if (!N8N_WEBHOOK_URL) {
    throw new Error('N8N webhook URL not configured. Set VITE_N8N_WEBHOOK_URL in .env');
  }

  return fetch(N8N_WEBHOOK_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chatInput: payload.chatInput,
      sessionId: payload.sessionId,
    }),
  });
}
