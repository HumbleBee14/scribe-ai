"use client";

import { useState } from "react";
import Image from "next/image";
import {
  AlertTriangle,
  Bot,
  Check,
  Copy,
  Loader2,
  ShieldAlert,
  User,
} from "lucide-react";
import { ImageLightbox } from "@/components/ui/image-lightbox";
import {
  FollowUpSuggestions,
  InlineBlock,
  PageImageBlock,
  TextBubble,
  ToolCallsSection,
} from "@/components/chat/message-bubble-parts";
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
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard not available */ }
  };

  return (
    <div className={`group/msg flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-orange-500" : "bg-slate-600 dark:bg-slate-500"
        }`}
      >
        {isUser ? (
          <User suppressHydrationWarning className="h-4 w-4 text-white" />
        ) : (
          <Bot suppressHydrationWarning className="h-4 w-4 text-white" />
        )}
      </div>

      {/* Content */}
      <div className={`flex flex-col gap-2 ${isUser ? "max-w-[85%] items-end" : "max-w-[90%]"}`}>
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
                  <Image
                    src={src}
                    alt={`Uploaded reference ${i + 1}`}
                    unoptimized
                    width={64}
                    height={64}
                    className="h-16 w-16 rounded-lg object-cover border border-gray-200 dark:border-neutral-700 hover:opacity-90 transition-opacity"
                  />
                </button>
              );
            })}
          </div>
        )}

        {lightboxSrc && (
          <ImageLightbox
            src={lightboxSrc}
            alt="Message image preview"
            title="Message image"
            onClose={() => setLightboxSrc(null)}
          />
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
            <ShieldAlert suppressHydrationWarning className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{warning.content}</span>
          </div>
        ))}

        {/* Tool calls: show only during streaming; collapse when done */}
        <ToolCallsSection toolCalls={message.toolCalls} isStreaming={!!message.isStreaming} />

        {/* Interleaved content blocks (text, artifacts, images in arrival order) */}
        {/* Consecutive image blocks are grouped into a flex-wrap row */}
        {message.blocks && message.blocks.length > 0 ? (
          (() => {
            const groups: Array<{ type: "single"; index: number } | { type: "images"; indices: number[] }> = [];
            for (let i = 0; i < message.blocks.length; i++) {
              if (message.blocks[i].type === "image") {
                const last = groups[groups.length - 1];
                if (last && last.type === "images") {
                  last.indices.push(i);
                } else {
                  groups.push({ type: "images", indices: [i] });
                }
              } else {
                groups.push({ type: "single", index: i });
              }
            }
            return groups.map((group, gi) => {
              if (group.type === "single") {
                return (
                  <InlineBlock
                    key={gi}
                    block={message.blocks![group.index]}
                    isUser={isUser}
                    isStreaming={!!message.isStreaming}
                    onSelectSourcePage={onSelectSourcePage}
                    onImageClick={setLightboxSrc}
                  />
                );
              }
              return (
                <div key={gi} className="flex flex-wrap gap-3 justify-center">
                  {group.indices.map((idx) => (
                    <InlineBlock
                      key={idx}
                      block={message.blocks![idx]}
                      isUser={isUser}
                      isStreaming={!!message.isStreaming}
                      onSelectSourcePage={onSelectSourcePage}
                      onImageClick={setLightboxSrc}
                    />
                  ))}
                </div>
              );
            });
          })()
        ) : (
          /* Fallback for old messages without blocks */
          <>
            {message.content && (
              <TextBubble
                text={message.content}
                isUser={isUser}
                onSelectSourcePage={onSelectSourcePage}
              />
            )}
            {message.pageImages?.map((img, idx) => (
              <PageImageBlock
                key={idx}
                img={img}
                onSelectSourcePage={onSelectSourcePage}
                onImageClick={setLightboxSrc}
              />
            ))}
          </>
        )}

        {/* Clarification card */}
        {message.clarification && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle suppressHydrationWarning className="mt-0.5 h-4 w-4 text-blue-500 dark:text-blue-400 shrink-0" />
              <div>
                <p className="text-sm text-blue-700 dark:text-blue-200">
                  {message.clarification.question}
                </p>
                {message.clarification.options && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {message.clarification.options.map((opt, i) => (
                      <button
                        key={i}
                        type="button"
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

        {/* Clickable follow-up suggestions (extracted from assistant text) */}
        {!isUser && !message.isStreaming && message.content && (
          <FollowUpSuggestions text={message.content} onSelect={onQuickReply} />
        )}

        {/* Generating indicator: at the bottom, while agent is still working */}
        {message.isStreaming && (
          <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-neutral-400 py-1">
            <Loader2 suppressHydrationWarning className="h-4 w-4 animate-spin text-orange-400" />
            <span>
              {!message.content && !(message.toolCalls?.length)
                ? "Thinking..."
                : "Generating response..."}
            </span>
          </div>
        )}
      </div>

      {/* Copy button: right side for assistant, left side for user (flex-row-reverse) */}
      {message.content && !message.isStreaming && (
        <button
          type="button"
          onClick={handleCopy}
          className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-gray-300 dark:text-neutral-600 hover:text-gray-500 dark:hover:text-neutral-400 focus:text-gray-500 dark:focus:text-neutral-400 transition-colors opacity-0 group-hover/msg:opacity-100 group-focus-within/msg:opacity-100"
          title="Copy"
        >
          {copied ? (
            <Check suppressHydrationWarning className="h-3.5 w-3.5 text-green-500" />
          ) : (
            <Copy suppressHydrationWarning className="h-3.5 w-3.5" />
          )}
        </button>
      )}
    </div>
  );
}
