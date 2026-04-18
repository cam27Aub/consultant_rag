import { useEffect, useRef, useState, useCallback } from 'react';
import type { Conversation, ChatMessage } from '../lib/types';
import { sendToN8n } from '../lib/n8nClient';
import { parseN8nResponse } from '../lib/responseParser';
import { MessageBubble } from './MessageBubble';
import { InputBar } from './InputBar';
import { ThinkingIndicator } from './ThinkingIndicator';
import { BRANDING } from '../constants/branding';
import { Menu, Search } from 'lucide-react';

interface ChatAreaProps {
  conversation: Conversation | null;
  onUpdate: (id: string, messages: Conversation['messages']) => void;
  onNewChat: () => Conversation;
  onToggleSidebar: () => void;
}

export function ChatArea({ conversation, onUpdate, onNewChat, onToggleSidebar }: ChatAreaProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages, isLoading]);

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    console.log('[ConsultantIQ] handleSend fired:', text);
    // Ensure we have a conversation — create one if needed
    const convo = conversation ?? onNewChat();

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text.trim(),
      responseType: 'text',
      timestamp: Date.now(),
    };

    const updatedMessages = [...convo.messages, userMessage];
    onUpdate(convo.id, updatedMessages);
    setIsLoading(true);

    try {
      const response = await sendToN8n({
        chatInput: text.trim(),
        sessionId: convo.id,
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const parsed = await parseN8nResponse(response);

      const assistantMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: parsed.content,
        responseType: parsed.type,
        fileName: parsed.fileName,
        downloadUrl: parsed.downloadUrl,
        timestamp: Date.now(),
      };

      onUpdate(convo.id, [...updatedMessages, assistantMessage]);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Something went wrong';
      const errorMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Error: ${errorMsg}`,
        responseType: 'text',
        timestamp: Date.now(),
      };
      onUpdate(convo.id, [...updatedMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [conversation, onNewChat, onUpdate, isLoading]);

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
        <div className="max-w-5xl mx-auto w-full">
          {conversation.messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {isLoading && <ThinkingIndicator />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <InputBar onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
