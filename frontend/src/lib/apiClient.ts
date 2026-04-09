/**
 * API client for persistent chat memory (Cosmos DB backend).
 * Syncs conversations and user preferences to the server.
 */

import type { Conversation } from './types';

// Use relative URLs — frontend is served from the same FastAPI server
const API_BASE = import.meta.env.VITE_API_URL || '';

// ── Conversations ─────────────────────────────────────────

export async function fetchConversations(): Promise<Conversation[]> {
  try {
    const res = await fetch(`${API_BASE}/conversations`);
    if (!res.ok) return [];
    const items = await res.json();

    // Server returns conversations without messages for the list view
    // We need to fetch each one individually for full messages
    return items.map((item: any) => ({
      id: item.id,
      title: item.title || 'New Chat',
      messages: item.messages || [],
      createdAt: item.createdAt || 0,
      updatedAt: item.updatedAt || 0,
    }));
  } catch {
    console.warn('[apiClient] Failed to fetch conversations from server');
    return [];
  }
}

export async function fetchConversation(id: string): Promise<Conversation | null> {
  try {
    const res = await fetch(`${API_BASE}/conversations/${id}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    console.warn(`[apiClient] Failed to fetch conversation ${id}`);
    return null;
  }
}

export async function syncConversation(conversation: Conversation): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(conversation),
    });
    return res.ok;
  } catch {
    console.warn('[apiClient] Failed to sync conversation to server');
    return false;
  }
}

export async function deleteConversationFromServer(id: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/conversations/${id}`, {
      method: 'DELETE',
    });
    return res.ok;
  } catch {
    console.warn(`[apiClient] Failed to delete conversation ${id}`);
    return false;
  }
}

// ── User Preferences ──────────────────────────────────────

export async function fetchUserProfile(): Promise<Record<string, string>> {
  try {
    const res = await fetch(`${API_BASE}/user-profile`);
    if (!res.ok) return {};
    return await res.json();
  } catch {
    console.warn('[apiClient] Failed to fetch user profile');
    return {};
  }
}

export async function updateUserProfile(preferences: Record<string, string>): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/user-profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preferences }),
    });
    return res.ok;
  } catch {
    console.warn('[apiClient] Failed to update user profile');
    return false;
  }
}
