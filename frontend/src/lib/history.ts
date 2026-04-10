"use client";

export interface ConversationSummary {
  id: string;
  productId: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

const STORAGE_KEY = "prox_conversations";

export function listConversations(productId: string): ConversationSummary[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return (JSON.parse(raw) as ConversationSummary[])
      .filter((conv) => conv.productId === productId)
      .sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

export function saveConversation(productId: string, conv: ConversationSummary): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const existing = raw ? (JSON.parse(raw) as ConversationSummary[]) : [];
    const filtered = existing.filter(
      (c) => !(c.productId === productId && c.id === conv.id)
    );
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ ...conv, productId }, ...filtered])
    );
  } catch {
    // Storage full or unavailable
  }
}

export function deleteConversation(productId: string, id: string): void {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const existing = raw ? (JSON.parse(raw) as ConversationSummary[]) : [];
    const filtered = existing.filter((c) => !(c.productId === productId && c.id === id));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));
  } catch {}
}

export function getMessageStorageKey(productId: string, conversationId: string): string {
  return `prox_msgs_${productId}_${conversationId}`;
}

export function deleteConversationMessages(productId: string, conversationId: string): void {
  try {
    localStorage.removeItem(getMessageStorageKey(productId, conversationId));
  } catch {}
}

export function listAllConversations(): ConversationSummary[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ConversationSummary[];
  } catch {
    return [];
  }
}

export function saveAllConversations(conversations: ConversationSummary[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch {}
}
