export type MessageRole = 'user' | 'assistant';
export type ResponseType = 'text' | 'file_download' | 'link_download' | 'cta' | 'async_pending';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  responseType: ResponseType;
  fileName?: string;
  downloadUrl?: string;
  ctaOptions?: string[];
  timestamp: number;
  sessionId?: string; // set on async_pending messages for polling
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface N8nPayload {
  chatInput: string;
  sessionId: string;
}

export interface ParsedResponse {
  type: ResponseType;
  content: string;
  fileName?: string;
  downloadUrl?: string;
  ctaOptions?: string[];
}
