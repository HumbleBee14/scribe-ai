"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import {
  ConversationSummary,
  deleteConversation,
  listConversations,
} from "@/lib/history";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export function HistorySidebar({ activeId, onSelect, onNew }: Props) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);

  useEffect(() => {
    setConversations(listConversations());
  }, [activeId]); // Reload when active conversation changes (new messages added)

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteConversation(id);
    setConversations(listConversations());
    if (id === activeId) onNew();
  };

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-800 px-4 py-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-neutral-500">
          History
        </span>
        <button
          onClick={onNew}
          className="flex h-6 w-6 items-center justify-center rounded-md text-gray-400 dark:text-neutral-500 hover:bg-gray-100 dark:hover:bg-neutral-800 hover:text-gray-700 dark:hover:text-neutral-200 transition-colors"
          title="New conversation"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-gray-400 dark:text-neutral-600">
            No conversations yet.
            <br />
            Start chatting!
          </div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => onSelect(conv.id)}
              className={`group flex cursor-pointer items-start gap-2 px-3 py-2.5 mx-1 rounded-lg transition-colors ${
                conv.id === activeId
                  ? "bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300"
                  : "text-gray-700 dark:text-neutral-300 hover:bg-gray-100 dark:hover:bg-neutral-800"
              }`}
            >
              <MessageSquare className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-50" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs font-medium">{conv.title}</div>
                <div className="text-[10px] text-gray-400 dark:text-neutral-500">
                  {conv.messageCount} {conv.messageCount === 1 ? "message" : "messages"}
                </div>
              </div>
              <button
                onClick={(e) => handleDelete(e, conv.id)}
                className="mt-0.5 hidden h-4 w-4 shrink-0 items-center justify-center rounded text-gray-400 hover:text-red-500 dark:text-neutral-500 dark:hover:text-red-400 group-hover:flex"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
