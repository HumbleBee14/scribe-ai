"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageSquare, PanelLeftClose, Pencil, PenSquare, Trash2 } from "lucide-react";
import {
  listConversations as listConversationsAPI,
  deleteConversationAPI,
  updateConversationTitle,
  type ConversationSummary,
} from "@/lib/api";

/** Tailwind width classes for the history rail. */
export const HISTORY_SIDEBAR_WIDTH_CLASS = "w-60 shrink-0";

interface Props {
  productId: string;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onCollapse: () => void;
}

export function HistorySidebar({
  productId,
  activeId,
  onSelect,
  onNew,
  onCollapse,
}: Props) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);

  const reload = useCallback(async () => {
    const convs = await listConversationsAPI(productId);
    setConversations(convs);
  }, [productId]);

  // Reload on mount and when activeId changes (new conversation created)
  useEffect(() => {
    void reload();
  }, [activeId, reload]);

  const handleDelete = async (id: string) => {
    await deleteConversationAPI(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (id === activeId) onNew();
  };

  const handleRename = async (id: string, title: string) => {
    await updateConversationTitle(id, title);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title } : c))
    );
  };

  return (
    <aside
      className={`flex min-h-0 flex-col border-r border-gray-200 bg-white dark:border-neutral-700 dark:bg-neutral-950 ${HISTORY_SIDEBAR_WIDTH_CLASS}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-3 py-2.5">
        <button
          onClick={onCollapse}
          className="flex h-7 w-7 items-center justify-center rounded-md text-gray-400 dark:text-neutral-400 hover:bg-gray-100 dark:hover:bg-neutral-800 hover:text-gray-700 dark:hover:text-neutral-200 transition-colors"
          title="Hide history"
        >
          <PanelLeftClose suppressHydrationWarning className="h-4 w-4" />
        </button>
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-neutral-400">
          History
        </span>
        <button
          onClick={onNew}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-orange-500 hover:bg-orange-50 dark:hover:bg-orange-950/40 transition-colors"
          title="New conversation"
        >
          <PenSquare suppressHydrationWarning className="h-3.5 w-3.5" />
          New
        </button>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-gray-400 dark:text-neutral-400">
            No conversations yet.
            <br />
            Start chatting!
          </div>
        ) : (
          conversations.map((conv) => (
            <ConversationRow
              key={conv.id}
              conv={conv}
              isActive={conv.id === activeId}
              onSelect={() => onSelect(conv.id)}
              onDelete={() => void handleDelete(conv.id)}
              onRename={(title) => void handleRename(conv.id, title)}
            />
          ))
        )}
      </div>
    </aside>
  );
}

function ConversationRow({
  conv,
  isActive,
  onSelect,
  onDelete,
  onRename,
}: {
  conv: ConversationSummary;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}) {
  const [editing, setEditing] = useState(false);

  const startEditing = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setEditing(true);
  };

  return (
    <div
      onClick={() => !editing && onSelect()}
      className={`group flex cursor-pointer items-start gap-2 px-3 py-2.5 mx-1 rounded-lg transition-colors ${
        isActive
          ? "bg-orange-50 dark:bg-orange-950/40 text-orange-700 dark:text-orange-300"
          : "text-gray-700 dark:text-neutral-300 hover:bg-gray-100 dark:hover:bg-neutral-800"
      }`}
    >
      <MessageSquare suppressHydrationWarning className="mt-0.5 h-3.5 w-3.5 shrink-0 opacity-50" />
      <div className="min-w-0 flex-1">
        <EditableTitle
          conv={conv}
          editing={editing}
          onRename={(title) => {
            onRename(title);
            setEditing(false);
          }}
          onEditDone={() => setEditing(false)}
        />
        <div className="text-[10px] text-gray-400 dark:text-neutral-400">
          {conv.message_count} {conv.message_count === 1 ? "message" : "messages"}
        </div>
      </div>
      {!editing && (
        <div className="mt-0.5 hidden shrink-0 items-center gap-1 group-hover:flex">
          <button
            type="button"
            onClick={startEditing}
            className="flex h-4 w-4 items-center justify-center rounded text-gray-400 hover:text-gray-600 dark:text-neutral-400 dark:hover:text-neutral-300"
            title="Rename"
          >
            <Pencil suppressHydrationWarning className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="flex h-4 w-4 items-center justify-center rounded text-gray-400 hover:text-red-500 dark:text-neutral-400 dark:hover:text-red-400"
            title="Delete"
          >
            <Trash2 suppressHydrationWarning className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
}

function EditableTitle({
  conv,
  editing,
  onRename,
  onEditDone,
}: {
  conv: ConversationSummary;
  editing: boolean;
  onRename: (title: string) => void;
  onEditDone: () => void;
}) {
  const [value, setValue] = useState(conv.title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) {
      const timeoutId = window.setTimeout(() => {
        setValue(conv.title);
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 0);
      return () => window.clearTimeout(timeoutId);
    }
  }, [editing, conv.title]);

  const save = () => {
    const trimmed = value.trim();
    if (trimmed && trimmed !== conv.title) {
      onRename(trimmed);
    } else {
      onEditDone();
    }
  };

  if (editing) {
    return (
      <div onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") onEditDone();
          }}
          onBlur={save}
          className="w-full rounded border border-gray-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-1.5 py-0.5 text-xs font-medium text-gray-900 dark:text-neutral-100 outline-none focus:border-orange-400"
        />
      </div>
    );
  }

  return <div className="truncate text-xs font-medium">{conv.title}</div>;
}
