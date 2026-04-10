"use client";

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

const STORAGE_KEY = "prox_conversations";

export function listConversations(): ConversationSummary[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return (JSON.parse(raw) as ConversationSummary[]).sort(
      (a, b) => b.updatedAt - a.updatedAt
    );
  } catch {
    return [];
  }
}

export function saveConversation(conv: ConversationSummary): void {
  try {
    const existing = listConversations().filter((c) => c.id !== conv.id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([conv, ...existing]));
  } catch {
    // Storage full or unavailable
  }
}

export function deleteConversation(id: string): void {
  try {
    const existing = listConversations().filter((c) => c.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
  } catch {}
}
