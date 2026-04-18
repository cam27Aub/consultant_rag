import { useState, useCallback, useEffect, useRef } from 'react';
import type { Conversation, ChatMessage } from '../lib/types';
import {
  fetchConversations,
  fetchConversation,
  syncConversation,
  deleteConversationFromServer,
} from '../lib/apiClient';

const STORAGE_KEY = 'consultantiq_conversations';
const MAX_AGE_DAYS = 30;

// ── localStorage helpers (offline fallback) ────────────────

function loadFromLocalStorage(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const convos: Conversation[] = JSON.parse(raw);
    const cutoff = Date.now() - MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
    return convos.filter((c) => c.updatedAt > cutoff).sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

function saveToLocalStorage(convos: Conversation[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(convos));
  } catch (e) {
    if (e instanceof DOMException && e.name === 'QuotaExceededError') {
      const pruned = convos.slice(0, Math.floor(convos.length / 2));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(pruned));
    }
  }
}

// ── Hook ───────────────────────────────────────────────────

export function useChatHistory() {
  const [conversations, setConversations] = useState<Conversation[]>(loadFromLocalStorage);
  const [activeId, setActiveId] = useState<string | null>(
    () => loadFromLocalStorage()[0]?.id ?? null
  );
  const [isLoaded, setIsLoaded] = useState(false);
  const syncTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Load from server on mount ────────────────────────────
  useEffect(() => {
    let cancelled = false;

    async function loadFromServer() {
      try {
        const serverConvos = await fetchConversations();

        if (cancelled || serverConvos.length === 0) {
          setIsLoaded(true);
          return;
        }

        // Fetch full messages for each conversation
        const fullConvos = await Promise.all(
          serverConvos.map(async (c) => {
            const full = await fetchConversation(c.id);
            return full || c;
          })
        );

        if (cancelled) return;

        // Merge: server data wins, but keep local-only conversations
        const serverIds = new Set(fullConvos.map((c) => c.id));
        const localOnly = loadFromLocalStorage().filter((c) => !serverIds.has(c.id));
        const merged = [...fullConvos, ...localOnly].sort((a, b) => b.updatedAt - a.updatedAt);

        setConversations(merged);
        saveToLocalStorage(merged);

        // Sync any local-only conversations to server
        for (const local of localOnly) {
          syncConversation(local);
        }

        if (!cancelled) {
          setActiveId((prev) => prev ?? merged[0]?.id ?? null);
          setIsLoaded(true);
        }
      } catch {
        console.warn('[useChatHistory] Server load failed, using localStorage');
        setIsLoaded(true);
      }
    }

    loadFromServer();
    return () => { cancelled = true; };
  }, []);

  // ── Sync to localStorage on every change ─────────────────
  useEffect(() => {
    saveToLocalStorage(conversations);
  }, [conversations]);

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;

  // ── Debounced server sync ────────────────────────────────
  const debouncedSync = useCallback((conversation: Conversation) => {
    if (syncTimeoutRef.current) {
      clearTimeout(syncTimeoutRef.current);
    }
    syncTimeoutRef.current = setTimeout(() => {
      syncConversation(conversation);
    }, 500); // Wait 500ms after last update before syncing
  }, []);

  // ── CRUD operations ──────────────────────────────────────

  const createConversation = useCallback((): Conversation => {
    const newConvo: Conversation = {
      id: crypto.randomUUID(),
      title: 'New Chat',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setConversations((prev) => [newConvo, ...prev]);
    setActiveId(newConvo.id);
    syncConversation(newConvo); // Sync immediately on create
    return newConvo;
  }, []);

  const updateConversation = useCallback((id: string, messages: ChatMessage[]) => {
    setConversations((prev) => {
      const updated = prev.map((c) => {
        if (c.id !== id) return c;
        const title =
          c.title === 'New Chat' && messages.length > 0
            ? messages[0].content.slice(0, 50) + (messages[0].content.length > 50 ? '...' : '')
            : c.title;
        const updatedConvo = { ...c, messages, title, updatedAt: Date.now() };
        // Debounced sync to server
        debouncedSync(updatedConvo);
        return updatedConvo;
      });
      return updated;
    });
  }, [debouncedSync]);

  const renameConversation = useCallback((id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return;
    setConversations((prev) => {
      const updated = prev.map((c) => {
        if (c.id !== id) return c;
        const renamed = { ...c, title: trimmed, updatedAt: Date.now() };
        syncConversation(renamed);
        return renamed;
      });
      return updated;
    });
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      deleteConversationFromServer(id); // Sync delete to server
      if (activeId === id) {
        setActiveId(() => {
          const remaining = conversations.filter((c) => c.id !== id);
          return remaining[0]?.id ?? null;
        });
      }
    },
    [activeId, conversations]
  );

  return {
    conversations,
    activeConversation,
    activeId,
    isLoaded,
    setActiveId,
    createConversation,
    updateConversation,
    renameConversation,
    deleteConversation,
  };
}
