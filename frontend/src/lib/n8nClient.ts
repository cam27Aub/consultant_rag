import type { N8nPayload } from './types';

const N8N_WEBHOOK_URL = import.meta.env.VITE_N8N_WEBHOOK_URL || '';

// 8 minutes — covers long research tasks (~6min observed max)
const TIMEOUT_MS = 480_000;

export async function sendToN8n(payload: N8nPayload): Promise<Response> {
  console.log('[ConsultantIQ] Webhook URL:', N8N_WEBHOOK_URL);
  console.log('[ConsultantIQ] Sending:', payload);

  if (!N8N_WEBHOOK_URL) {
    throw new Error('N8N webhook URL not configured. Set VITE_N8N_WEBHOOK_URL in .env');
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  const asyncPending = new Response(JSON.stringify({ __async_pending: true }), {
    status: 202,
    headers: { 'Content-Type': 'application/json' },
  });

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

    // 524 = Cloudflare timeout, 504 = gateway timeout, 502 = bad gateway
    // The n8n workflow is still running — switch to async polling mode.
    if (response.status === 524 || response.status === 504 ||
        response.status === 502 || response.status === 408) {
      return asyncPending;
    }

    return response;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    // Any network error — workflow still running, switch to async polling.
    return asyncPending;
  }
}
