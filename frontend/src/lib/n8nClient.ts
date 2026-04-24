import type { N8nPayload } from './types';

const N8N_WEBHOOK_URL = import.meta.env.VITE_N8N_WEBHOOK_URL || '';

// 3 minutes — comfortably above the 2m30s max execution time
const TIMEOUT_MS = 180_000;

export async function sendToN8n(payload: N8nPayload): Promise<Response> {
  console.log('[ConsultantIQ] Webhook URL:', N8N_WEBHOOK_URL);
  console.log('[ConsultantIQ] Sending:', payload);

  if (!N8N_WEBHOOK_URL) {
    throw new Error('N8N webhook URL not configured. Set VITE_N8N_WEBHOOK_URL in .env');
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(N8N_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chatInput: payload.chatInput,
        sessionId: payload.sessionId,
      }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    // n8n closes the connection after ~2min regardless of our timeout.
    // Treat ANY network error as async_pending — the workflow is still
    // running and will push the result via HTTP Request → /async-result.
    return new Response(JSON.stringify({ __async_pending: true }), {
      status: 202,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
