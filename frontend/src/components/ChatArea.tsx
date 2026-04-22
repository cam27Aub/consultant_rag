import { useEffect, useRef, useState, useCallback } from 'react';
import type { Conversation, ChatMessage } from '../lib/types';
import { sendToN8n } from '../lib/n8nClient';
import { parseN8nResponse } from '../lib/responseParser';
import { MessageBubble } from './MessageBubble';
import { InputBar } from './InputBar';
import { ThinkingIndicator } from './ThinkingIndicator';
import { BRANDING } from '../constants/branding';
import { Menu, Search } from 'lucide-react';

const BASE = import.meta.env.VITE_API_URL ?? '';
const POLL_INTERVAL_MS = 4000;

interface ChatAreaProps {
  conversation: Conversation | null;
  onUpdate: (id: string, messages: Conversation['messages']) => void;
  onNewChat: () => Conversation;
  onToggleSidebar: () => void;
}

export function ChatArea({ conversation, onUpdate, onNewChat, onToggleSidebar }: ChatAreaProps) {
  const messagesEndRef   = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Polling refs — persist across renders without triggering re-renders
  const pollTimerRef     = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingMsgIdRef  = useRef<string | null>(null);
  const convIdRef        = useRef<string | null>(null);
  const messagesRef      = useRef<ChatMessage[]>([]);

  // Keep messagesRef in sync with the current conversation
  useEffect(() => {
    messagesRef.current = conversation?.messages ?? [];
  }, [conversation?.messages]);

  // Clean up polling on unmount
  useEffect(() => {
    return () => { if (pollTimerRef.current) clearInterval(pollTimerRef.current); };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages, isLoading]);

  // ── Polling: called when n8n times out and pushes result async ──
  const startPolling = useCallback((sessionId: string, pendingMsgId: string) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${BASE}/async-result/${sessionId}`);
        const data = await res.json();

        if (data.status === 'ready' && data.content) {
          clearInterval(pollTimerRef.current!);
          pollTimerRef.current  = null;
          pendingMsgIdRef.current = null;

          // Parse the result the same way a normal n8n response is parsed
          const fakeResponse = new Response(
            JSON.stringify({ output: data.content }),
            { headers: { 'content-type': 'application/json' } }
          );
          const parsed = await parseN8nResponse(fakeResponse);

          const realMsg: ChatMessage = {
            id:           pendingMsgId,   // same ID → replaces the pending bubble in-place
            role:         'assistant',
            content:      parsed.content,
            responseType: parsed.type,
            fileName:     parsed.fileName,
            downloadUrl:  parsed.downloadUrl,
            ctaOptions:   parsed.ctaOptions,
            timestamp:    Date.now(),
          };

          // Replace the async_pending bubble with the real result
          const updated = messagesRef.current.map(m =>
            m.id === pendingMsgId ? realMsg : m
          );
          onUpdate(convIdRef.current!, updated);
        }
      } catch { /* silent — keep polling */ }
    }, POLL_INTERVAL_MS);
  }, [onUpdate]);

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    console.log('[ConsultantIQ] handleSend fired:', text);
    const convo = conversation ?? onNewChat();
    convIdRef.current = convo.id;

    const userMessage: ChatMessage = {
      id:           crypto.randomUUID(),
      role:         'user',
      content:      text.trim(),
      responseType: 'text',
      timestamp:    Date.now(),
    };

    const updatedMessages = [...convo.messages, userMessage];
    onUpdate(convo.id, updatedMessages);
    setIsLoading(true);

    try {
      const response = await sendToN8n({
        chatInput: text.trim(),
        sessionId: convo.id,
      });

      if (!response.ok && response.status !== 202) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const parsed = await parseN8nResponse(response);

      if (parsed.type === 'async_pending') {
        // n8n timed out — show a "Research in progress" bubble and start polling
        const pendingMsgId = crypto.randomUUID();
        pendingMsgIdRef.current = pendingMsgId;

        const pendingMsg: ChatMessage = {
          id:           pendingMsgId,
          role:         'assistant',
          content:      '',
          responseType: 'async_pending',
          sessionId:    convo.id,
          timestamp:    Date.now(),
        };

        const withPending = [...updatedMessages, pendingMsg];
        messagesRef.current = withPending;
        onUpdate(convo.id, withPending);
        setIsLoading(false);  // unlock input — user can keep chatting
        startPolling(convo.id, pendingMsgId);
        return;
      }

      const assistantMessage: ChatMessage = {
        id:           crypto.randomUUID(),
        role:         'assistant',
        content:      parsed.content,
        responseType: parsed.type,
        fileName:     parsed.fileName,
        downloadUrl:  parsed.downloadUrl,
        ctaOptions:   parsed.ctaOptions,
        timestamp:    Date.now(),
      };

      onUpdate(convo.id, [...updatedMessages, assistantMessage]);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Something went wrong';
      const errorMessage: ChatMessage = {
        id:           crypto.randomUUID(),
        role:         'assistant',
        content:      `Error: ${errorMsg}`,
        responseType: 'text',
        timestamp:    Date.now(),
      };
      onUpdate(convo.id, [...updatedMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [conversation, onNewChat, onUpdate, isLoading, startPolling]);

  // Welcome screen
  if (!conversation || conversation.messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col bg-sparc-bg">
        <div className="flex items-center gap-3 px-4 py-3 border-b border-sparc-border bg-white">
          <button onClick={onToggleSidebar} className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100">
            <Menu className="w-5 h-5 text-sparc-text" />
          </button>
          <h2 className="text-sm font-semibold text-navy">{BRANDING.appName}</h2>
        </div>

        <div className="flex-1 flex items-center justify-center p-6">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 rounded-2xl bg-navy flex items-center justify-center mx-auto mb-4">
              <Search className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-2xl font-bold text-navy mb-2">{BRANDING.appName}</h2>
            <p className="text-sm text-sparc-muted">
              Research intelligence powered by {BRANDING.companyName}. Ask anything, get data-backed insights, reports, and presentations.
            </p>
          </div>
        </div>

        <InputBar onSend={handleSend} disabled={isLoading} />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-sparc-bg">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-sparc-border bg-white">
        <button onClick={onToggleSidebar} className="lg:hidden p-1.5 rounded-lg hover:bg-gray-100">
          <Menu className="w-5 h-5 text-sparc-text" />
        </button>
        <h2 className="text-sm font-semibold text-navy truncate">{conversation.title}</h2>
      </div>

      <div className="flex-1 overflow-y-auto py-4">
        <div className="w-full px-4">
          {conversation.messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} onCTAClick={handleSend} />
          ))}
          {isLoading && <ThinkingIndicator />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <InputBar onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
