export type MessageRole = 'user' | 'assistant';
export type ResponseType = 'text' | 'file_download' | 'link_download' | 'cta';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  responseType: ResponseType;
  fileName?: string;
  downloadUrl?: string;
  ctaOptions?: string[];
  timestamp: number;
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
