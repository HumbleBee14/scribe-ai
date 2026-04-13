"use client";

import { useMemo, useState } from "react";
import Image from "next/image";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  Expand,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { buildBackendUrl } from "@/lib/api";
import { parseArtifactSegments } from "@/lib/artifacts";
import { ArtifactModal, renderArtifactByType } from "@/components/artifacts/artifact-modal";
import type {
  ArtifactEvent,
  ContentBlock,
  ImageEvent,
  SelectedSourcePage,
} from "@/types/events";

// Matches "pages 3, 4, 5, 7, 14-17" or "page 3" or "pages 3-5" or "pages 19 & 23" or "pages 1 and 5"
// Captures the full list including commas, ampersands, "and", ranges, and spaces
const PAGE_LIST_REGEX =
  /\b(?:manual\s*,?\s*)?(?:pages?\s*\.?\s*)(\d{1,3}(?:\s*[-\u2013]\s*\d{1,3})?(?:\s*(?:,|&|and)\s*\d{1,3}(?:\s*[-\u2013]\s*\d{1,3})?)*)\b/gi;
// Matches individual page numbers or ranges within a matched list
const PAGE_NUM_REGEX = /(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?/g;
const FOLLOWUPS_BLOCK_REGEX = /```followups\n([\s\S]*?)```/gi;

function processChildren(
  children: React.ReactNode,
  transform: (text: string) => React.ReactNode,
): React.ReactNode {
  if (typeof children === "string") return transform(children);
  if (Array.isArray(children)) {
    return children.map((child, index) =>
      typeof child === "string" ? <span key={index}>{transform(child)}</span> : child
    );
  }
  return children;
}

function makePageButton(
  page: number,
  label: string,
  key: string,
  onSelect: (source: SelectedSourcePage) => void,
  pages?: number[],
) {
  return (
    <button
      key={key}
      type="button"
      onClick={() =>
        onSelect({
          page,
          pages: pages && pages.length > 1 ? pages : undefined,
          title: pages && pages.length > 1 ? `Pages ${pages[0]}-${pages[pages.length - 1]}` : `Page ${page}`,
        })
      }
      className="inline text-orange-500 hover:text-orange-600 underline underline-offset-2 cursor-pointer"
    >
      {label}
    </button>
  );
}

function linkifyPageRefs(
  children: React.ReactNode,
  onSelect?: (source: SelectedSourcePage) => void,
): React.ReactNode {
  if (!onSelect) return children;
  return processChildren(children, (text) => {
    const parts: React.ReactNode[] = [];
    let lastIdx = 0;
    let match: RegExpExecArray | null;
    const regex = new RegExp(PAGE_LIST_REGEX.source, "gi");

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        parts.push(text.slice(lastIdx, match.index));
      }

      // "pages " prefix part (everything before the first digit)
      const fullMatch = match[0];
      const numListStr = match[1];
      const prefix = fullMatch.slice(0, fullMatch.indexOf(numListStr));
      parts.push(prefix);

      // Now linkify each page number/range within the list
      const numRegex = new RegExp(PAGE_NUM_REGEX.source, "g");
      let numMatch: RegExpExecArray | null;
      let numLastIdx = 0;

      while ((numMatch = numRegex.exec(numListStr)) !== null) {
        // Push any separator (comma, space) between numbers
        if (numMatch.index > numLastIdx) {
          parts.push(numListStr.slice(numLastIdx, numMatch.index));
        }
        const startPage = parseInt(numMatch[1], 10);
        const endPage = numMatch[2] ? parseInt(numMatch[2], 10) : startPage;
        if (startPage >= 1) {
          const allPages: number[] = [];
          for (let p = startPage; p <= Math.min(endPage, startPage + 20); p++) {
            allPages.push(p);
          }
          parts.push(
            makePageButton(startPage, numMatch[0], `pref-${match.index}-${numMatch.index}`, onSelect, allPages)
          );
        } else {
          parts.push(numMatch[0]);
        }
        numLastIdx = numRegex.lastIndex;
      }
      if (numLastIdx < numListStr.length) {
        parts.push(numListStr.slice(numLastIdx));
      }

      lastIdx = regex.lastIndex;
    }

    if (lastIdx < text.length) parts.push(text.slice(lastIdx));
    return parts.length > 0 ? parts : text;
  });
}

function extractFollowUps(text: string): string[] {
  const questions: string[] = [];
  let match: RegExpExecArray | null;
  const regex = new RegExp(FOLLOWUPS_BLOCK_REGEX.source, "g");
  while ((match = regex.exec(text)) !== null) {
    const block = match[1];
    for (const line of block.split("\n")) {
      // Strip leading markdown list marker (-, *, or numbered)
      const cleaned = line.trim().replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, "");
      if (cleaned.length > 5) questions.push(cleaned);
    }
  }
  return questions;
}

export function stripFollowupsBlock(text: string): string {
  // Strip completed followups blocks
  let result = text.replace(FOLLOWUPS_BLOCK_REGEX, "");
  // Strip unclosed followups block (still streaming, closing ``` hasn't arrived)
  result = result.replace(/```followups\n[\s\S]*$/i, "");
  return result.trim();
}

export function FollowUpSuggestions({
  text,
  onSelect,
}: {
  text: string;
  onSelect?: (message: string) => void;
}) {
  const followUps = useMemo(() => extractFollowUps(text), [text]);
  if (followUps.length === 0 || !onSelect) return null;

  return (
    <div className="flex flex-wrap gap-2 pt-2">
      {followUps.map((question, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onSelect(question)}
          className="rounded-full border-2 border-gray-300 dark:border-neutral-600 bg-white dark:bg-neutral-800 px-4 py-2 text-xs font-medium text-gray-700 dark:text-neutral-200 shadow-sm hover:border-orange-400 dark:hover:border-orange-500 hover:text-orange-600 dark:hover:text-orange-300 hover:shadow-md transition-all text-left"
        >
          {question}
        </button>
      ))}
    </div>
  );
}

export function ToolCallsSection({
  toolCalls,
  isStreaming,
}: {
  toolCalls?: Array<{ tool: string; label: string; ok?: boolean }>;
  isStreaming: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const calls = useMemo(() => toolCalls ?? [], [toolCalls]);

  if (calls.length === 0) return null;

  if (isStreaming) {
    const seen = new Set<string>();
    const visible = calls.filter((toolCall) => {
      if (seen.has(toolCall.label)) return false;
      seen.add(toolCall.label);
      return true;
    });
    return (
      <div className="flex flex-col gap-1">
        {visible.map((toolCall, index) => (
          <div
            key={index}
            className="flex items-center gap-2 text-xs text-gray-400 dark:text-neutral-400"
          >
            {toolCall.ok === undefined ? (
              <Loader2 suppressHydrationWarning className="h-3 w-3 animate-spin text-orange-400" />
            ) : (
              <CheckCircle suppressHydrationWarning className="h-3 w-3 text-green-500" />
            )}
            <span>{toolCall.label}</span>
          </div>
        ))}
      </div>
    );
  }

  const uniqueLabels = [...new Set(calls.map((toolCall) => toolCall.label))];
  const summary = uniqueLabels.length === 1 ? uniqueLabels[0] : `${calls.length} steps`;

  return (
    <div className="text-xs">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex items-center gap-1.5 text-gray-400 dark:text-neutral-400 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors"
      >
        <CheckCircle suppressHydrationWarning className="h-3 w-3 text-green-500 shrink-0" />
        <span>{summary}</span>
        <ChevronDown
          suppressHydrationWarning
          className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>

      {expanded && (
        <div className="mt-1.5 ml-1 flex flex-col gap-1 border-l-2 border-gray-100 dark:border-neutral-800 pl-3">
          {calls.map((toolCall, index) => (
            <div
              key={index}
              className="flex items-center gap-2 text-gray-400 dark:text-neutral-400"
            >
              <CheckCircle suppressHydrationWarning className="h-2.5 w-2.5 text-green-500 shrink-0" />
              <span>{toolCall.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function PageImageBlock({
  img,
  onSelectSourcePage,
  onImageClick,
}: {
  img: ImageEvent["data"];
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
  onImageClick?: (src: string) => void;
}) {
  const url = buildBackendUrl(img.url);
  return (
    <div className="w-72 shrink-0 rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-2 text-xs text-gray-400 dark:text-neutral-400">
        <span>Manual Page {img.page}</span>
        <button
          type="button"
          onClick={() =>
            onSelectSourcePage?.({
              page: img.page,
              sourceId: img.source_id,
              title: `Manual Page ${img.page}`,
            })
          }
          className="inline-flex items-center gap-1 text-orange-500 hover:text-orange-600"
        >
          Open in sidebar
          <ExternalLink suppressHydrationWarning className="h-3 w-3" />
        </button>
      </div>
      <button type="button" onClick={() => onImageClick?.(url)} className="flex w-full justify-center overflow-hidden rounded-md bg-gray-50 px-10 py-5 dark:bg-neutral-800">
        <Image
          src={url}
          alt={`Manual page ${img.page}`}
          unoptimized
          width={480}
          height={360}
          className="max-h-72 w-auto rounded object-contain hover:opacity-90 transition-opacity"
        />
      </button>
    </div>
  );
}

function ArtifactSourceLinks({
  artifact,
  onSelectSourcePage,
}: {
  artifact: ArtifactEvent["data"];
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
}) {
  if (!artifact.source_pages.length || !onSelectSourcePage) return null;

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {artifact.source_pages.map((source, index) => (
        <button
          key={`${artifact.id}-source-${index}`}
          type="button"
          onClick={() =>
            onSelectSourcePage({
              page: source.page,
              title: artifact.title,
              description: source.description,
            })
          }
          className="rounded-full border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-800 px-3 py-1 text-xs text-gray-600 dark:text-neutral-300 hover:border-orange-300 dark:hover:border-orange-500 hover:text-orange-600 dark:hover:text-orange-300 transition-colors"
        >
          p.{source.page}
          {source.description ? ` · ${source.description}` : ""}
        </button>
      ))}
    </div>
  );
}

function InlineArtifact({
  artifact,
  onSelectSourcePage,
}: {
  artifact: ArtifactEvent["data"];
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
}) {
  const [zoomed, setZoomed] = useState(false);
  const type = artifact.renderer || artifact.type || "";

  return (
    <>
      <div className="relative group/art my-2">
        {renderArtifactByType(type, artifact.code, artifact.title)}
        <button
          type="button"
          onClick={() => setZoomed(true)}
          className="absolute top-2 right-2 hidden group-hover/art:flex h-7 w-7 items-center justify-center rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
          title="Expand"
        >
          <Expand suppressHydrationWarning className="h-3.5 w-3.5" />
        </button>
        <ArtifactSourceLinks artifact={artifact} onSelectSourcePage={onSelectSourcePage} />
      </div>
      {zoomed && (
        <ArtifactModal
          type={type}
          title={artifact.title}
          code={artifact.code}
          onClose={() => setZoomed(false)}
        />
      )}
    </>
  );
}

function ArtifactLoadingPlaceholder({
  renderer,
  title,
  partial,
}: {
  renderer: string;
  title: string;
  partial: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const charCount = partial.length;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 p-4 my-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Loader2 suppressHydrationWarning className="h-5 w-5 animate-spin text-orange-400 shrink-0" />
          <div>
            <div className="text-sm font-medium text-gray-700 dark:text-neutral-300">
              Generating {title || renderer || "artifact"}...
            </div>
            <div className="text-xs text-gray-400 dark:text-neutral-400 mt-0.5">
              {renderer.toUpperCase()}
              {charCount > 0 ? ` · ${charCount} chars received` : ""}
            </div>
          </div>
        </div>
        {charCount > 0 && (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="text-xs text-gray-400 dark:text-neutral-400 hover:text-gray-600 dark:hover:text-neutral-300 flex items-center gap-1"
          >
            <ChevronDown
              suppressHydrationWarning
              className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`}
            />
            {expanded ? "Hide" : "Show"} stream
          </button>
        )}
      </div>
      {expanded && partial && (
        <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-gray-100 dark:bg-neutral-950 p-3 text-xs text-gray-600 dark:text-neutral-400 font-mono whitespace-pre-wrap break-all">
          {partial}
        </pre>
      )}
    </div>
  );
}

export function TextBubble({
  text,
  isUser,
  onSelectSourcePage,
}: {
  text: string;
  isUser: boolean;
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
}) {
  if (isUser) {
    return (
      <div className="rounded-2xl rounded-br-none px-4 py-3 bg-orange-100 dark:bg-orange-950/50 text-gray-800 dark:text-orange-100 border border-orange-200 dark:border-orange-800/60">
        <div className="chat-prose chat-prose-user">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
      </div>
    );
  }

  const displayText = stripFollowupsBlock(text);
  if (!displayText.trim()) return null;

  return (
    <div className="chat-prose text-gray-900 dark:text-neutral-100">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{linkifyPageRefs(children, onSelectSourcePage)}</p>,
          li: ({ children }) => <li>{linkifyPageRefs(children, onSelectSourcePage)}</li>,
          strong: ({ children }) => (
            <strong>{linkifyPageRefs(children, onSelectSourcePage)}</strong>
          ),
          em: ({ children }) => <em>{linkifyPageRefs(children, onSelectSourcePage)}</em>,
        }}
      >
        {displayText}
      </ReactMarkdown>
    </div>
  );
}

export function InlineBlock({
  block,
  isUser,
  isStreaming,
  onSelectSourcePage,
  onImageClick,
}: {
  block: ContentBlock;
  isUser: boolean;
  isStreaming: boolean;
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
  onImageClick?: (src: string) => void;
}) {
  if (block.type === "artifact") {
    return <InlineArtifact artifact={block.data} onSelectSourcePage={onSelectSourcePage} />;
  }

  if (block.type === "image") {
    return (
      <PageImageBlock
        img={block.data}
        onSelectSourcePage={onSelectSourcePage}
        onImageClick={onImageClick}
      />
    );
  }

  if (block.type === "text" && block.text.trim()) {
    const displayText = stripFollowupsBlock(block.text);
    if (!displayText.trim()) return null;

    const segments = parseArtifactSegments(displayText);
    const hasSpecial = segments.some((segment) => segment.kind !== "text");

    if (!hasSpecial) {
      return (
        <TextBubble
          text={displayText}
          isUser={isUser}
          onSelectSourcePage={onSelectSourcePage}
        />
      );
    }

    return (
      <>
        {segments.map((segment, index) => {
          if (segment.kind === "text") {
            return (
              <TextBubble
                key={index}
                text={segment.text}
                isUser={isUser}
                onSelectSourcePage={onSelectSourcePage}
              />
            );
          }
          if (segment.kind === "artifact_loading") {
            if (!isStreaming && segment.partial.length > 50) {
              return (
                <InlineArtifact
                  key={index}
                  artifact={{
                    id: `truncated-${index}`,
                    renderer: segment.renderer,
                    title: segment.title || "Truncated artifact",
                    code: segment.partial,
                    source_pages: [],
                    type: segment.renderer,
                  }}
                  onSelectSourcePage={onSelectSourcePage}
                />
              );
            }
            return (
              <ArtifactLoadingPlaceholder
                key={index}
                renderer={segment.renderer}
                title={segment.title}
                partial={segment.partial}
              />
            );
          }
          return (
            <InlineArtifact
              key={index}
              artifact={{
                id: `parsed-${index}`,
                renderer: segment.artifact.renderer,
                title: segment.artifact.title,
                code: segment.artifact.code,
                source_pages: [],
                type: segment.artifact.renderer,
              }}
              onSelectSourcePage={onSelectSourcePage}
            />
          );
        })}
      </>
    );
  }

  return null;
}

export function AlertInlineError({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950 p-3">
      <div className="flex items-start gap-2 text-sm text-red-700 dark:text-red-200">
        <AlertCircle suppressHydrationWarning className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-medium">{title}</p>
          <p className="mt-1 text-xs opacity-90">{message}</p>
        </div>
      </div>
    </div>
  );
}
