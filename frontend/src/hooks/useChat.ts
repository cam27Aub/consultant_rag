import { useState, useCallback } from 'react';
import type { ChatMessage } from '../lib/types';
import { sendToN8n } from '../lib/n8nClient';
import { parseN8nResponse } from '../lib/responseParser';

interface UseChatOptions {
  conversationId: string;
  messages: ChatMessage[];
  onUpdate: (id: string, messages: ChatMessage[]) => void;
}

export function useChat({ conversationId, messages, onUpdate }: UseChatOptions) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: text.trim(),
        responseType: 'text',
        timestamp: Date.now(),
      };

      const updatedMessages = [...messages, userMessage];
      onUpdate(conversationId, updatedMessages);
      setIsLoading(true);
      setError(null);

      try {
        const response = await sendToN8n({
          chatInput: text.trim(),
          sessionId: conversationId,
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

        onUpdate(conversationId, [...updatedMessages, assistantMessage]);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Something went wrong';
        setError(errorMsg);

        const errorMessage: ChatMessage = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Error: ${errorMsg}`,
          responseType: 'text',
          timestamp: Date.now(),
        };
        onUpdate(conversationId, [...updatedMessages, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId, messages, onUpdate, isLoading]
  );

  return { isLoading, error, sendMessage };
}
