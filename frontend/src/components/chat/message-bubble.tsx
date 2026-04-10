"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Bot,
  CheckCircle,
  ChevronDown,
  ExternalLink,
  ImageIcon,
  Loader2,
  ShieldAlert,
  User,
  X,
} from "lucide-react";
import { buildBackendUrl } from "@/lib/api";
import { ArtifactRenderer } from "@/components/artifacts/artifact-renderer";
import type { ChatMessage, SelectedSourcePage } from "@/types/events";

interface Props {
  message: ChatMessage;
  onQuickReply?: (message: string) => void;
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
}

export function MessageBubble({
  message,
  onQuickReply,
  onSelectSourcePage,
}: Props) {
  const isUser = message.role === "user";
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!lightboxSrc) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxSrc(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightboxSrc]);

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-orange-500" : "bg-gray-200 dark:bg-neutral-700"
        }`}
      >
        {isUser ? (
          <User className="h-4 w-4 text-white" />
        ) : (
          <Bot className="h-4 w-4 text-white" />
        )}
      </div>

      {/* Content */}
      <div className={`flex max-w-[80%] flex-col gap-2 ${isUser ? "items-end" : ""}`}>
        {/* Uploaded user images: compact inline row, click to expand */}
        {message.images && message.images.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {message.images.map((img, i) => {
              const src = `data:${img.mediaType};base64,${img.data}`;
              return (
                <button
                  key={`${message.id}-upload-${i}`}
                  type="button"
                  onClick={() => setLightboxSrc(src)}
                  className="block shrink-0"
                  title="Click to expand"
                >
                  <img
                    src={src}
                    alt={`Uploaded reference ${i + 1}`}
                    className="h-16 w-16 rounded-lg object-cover border border-gray-200 dark:border-neutral-700 hover:opacity-90 transition-opacity"
                    loading="lazy"
                  />
                </button>
              );
            })}
          </div>
        )}

        {/* Lightbox */}
        {lightboxSrc && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => setLightboxSrc(null)}
          >
            <div
              className="relative max-h-[90vh] max-w-[90vw]"
              onClick={(e) => e.stopPropagation()}
            >
              <img
                src={lightboxSrc}
                alt="Preview"
                className="max-h-[85vh] max-w-[85vw] rounded-xl shadow-2xl object-contain"
              />
              <button
                onClick={() => setLightboxSrc(null)}
                className="absolute -right-3 -top-3 flex h-8 w-8 items-center justify-center rounded-full bg-white dark:bg-neutral-800 text-gray-700 dark:text-neutral-200 shadow-lg hover:bg-gray-100 dark:hover:bg-neutral-700 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Safety warnings */}
        {message.safetyWarnings?.map((warning, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
              warning.level === "danger"
                ? "bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-200"
                : "bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 text-yellow-700 dark:text-yellow-200"
            }`}
          >
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{warning.content}</span>
          </div>
        ))}

        {/* Tool calls: show only during streaming; collapse when done */}
        <ToolCallsSection toolCalls={message.toolCalls} isStreaming={!!message.isStreaming} />

        {/* Thinking indicator: show while tools run but no text yet */}
        {message.isStreaming && !message.content && (message.toolCalls?.length ?? 0) > 0 && (
          <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-neutral-500 py-1">
            <Loader2 className="h-4 w-4 animate-spin text-orange-400" />
            <span>Generating response...</span>
          </div>
        )}

        {/* Main text */}
        {message.content && (
          <div
            className={`rounded-2xl px-4 py-3 ${
              isUser
                ? "bg-orange-500 text-white"
                : "bg-white dark:bg-neutral-800 text-gray-900 dark:text-neutral-100 border border-gray-200 dark:border-neutral-700"
            }`}
          >
            <div className={`chat-prose ${isUser ? "chat-prose-user" : ""}`}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Page images */}
        {message.pageImages?.map((img, i) => (
          <div
            key={i}
            className="rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-2"
          >
            <div className="mb-1 flex items-center justify-between gap-2 text-xs text-gray-400 dark:text-neutral-400">
              <span>Manual Page {img.page}</span>
              <button
                onClick={() =>
                  onSelectSourcePage?.({
                    page: img.page,
                    title: `Manual Page ${img.page}`,
                  })
                }
                className="inline-flex items-center gap-1 text-orange-500 hover:text-orange-600 dark:text-orange-400 dark:hover:text-orange-300"
              >
                Open in sidebar
                <ExternalLink className="h-3 w-3" />
              </button>
            </div>
            <img
              src={buildBackendUrl(img.url)}
              alt={`Manual page ${img.page}`}
              className="max-h-80 rounded"
              loading="lazy"
            />
          </div>
        ))}

        {/* Artifacts: rendered via type-specific viewers */}
        {message.artifacts?.map((artifact, i) => (
          <ArtifactRenderer
            key={`${artifact.id}-${i}`}
            artifact={artifact}
            onSelectSourcePage={onSelectSourcePage}
          />
        ))}

        {/* Clarification card */}
        {message.clarification && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-blue-500 dark:text-blue-400 shrink-0" />
              <div>
                <p className="text-sm text-blue-700 dark:text-blue-200">
                  {message.clarification.question}
                </p>
                {message.clarification.options && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {message.clarification.options.map((opt, i) => (
                      <button
                        key={i}
                        onClick={() => onQuickReply?.(opt)}
                        className="rounded-full bg-blue-100 dark:bg-blue-900 px-3 py-1 text-xs text-blue-700 dark:text-blue-200 hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Streaming indicator */}
        {message.isStreaming && !message.content && (
          <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-neutral-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking...
          </div>
        )}

        {!isUser &&
          !message.pageImages?.length &&
          !message.artifacts?.length &&
          !message.content &&
          !message.isStreaming && (
            <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-neutral-500">
              <ImageIcon className="h-3.5 w-3.5" />
              No visual sources were returned for this answer.
            </div>
          )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ToolCallsSection: smart display of tool calls
// - During streaming: show each call as it happens (deduped by label)
// - After done: collapsed into a single "N steps" pill, expandable
// ---------------------------------------------------------------------------

interface ToolCall {
  tool: string;
  label: string;
  ok?: boolean;
}

function ToolCallsSection({
  toolCalls,
  isStreaming,
}: {
  toolCalls?: ToolCall[];
  isStreaming: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const calls = useMemo(() => toolCalls ?? [], [toolCalls]);
  const pending = calls.filter((t) => t.ok === undefined);
  const done = calls.filter((t) => t.ok !== undefined);

  if (calls.length === 0) return null;

  // While streaming: show only currently-running calls (deduped by label)
  if (isStreaming) {
    const seen = new Set<string>();
    const visible = calls.filter((t) => {
      if (seen.has(t.label)) return false;
      seen.add(t.label);
      return true;
    });
    return (
      <div className="flex flex-col gap-1">
        {visible.map((tc, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-gray-400 dark:text-neutral-500">
            {tc.ok === undefined ? (
              <Loader2 className="h-3 w-3 animate-spin text-orange-400" />
            ) : (
              <CheckCircle className="h-3 w-3 text-green-500" />
            )}
            <span>{tc.label}</span>
          </div>
        ))}
      </div>
    );
  }

  // After done: collapsed pill summarising what ran
  const uniqueLabels = [...new Set(calls.map((t) => t.label))];
  const summary =
    uniqueLabels.length === 1
      ? uniqueLabels[0]
      : `${calls.length} steps`;

  return (
    <div className="text-xs">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-gray-400 dark:text-neutral-500 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors"
      >
        <CheckCircle className="h-3 w-3 text-green-500 shrink-0" />
        <span>{summary}</span>
        <ChevronDown
          className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <div className="mt-1.5 ml-1 flex flex-col gap-1 border-l-2 border-gray-100 dark:border-neutral-800 pl-3">
          {calls.map((tc, i) => (
            <div key={i} className="flex items-center gap-2 text-gray-400 dark:text-neutral-500">
              <CheckCircle className="h-2.5 w-2.5 text-green-500 shrink-0" />
              <span>{tc.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
