"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Bot,
  Check,
  CheckCircle,
  ChevronDown,
  Copy,
  Expand,
  ExternalLink,
  ImageIcon,
  Loader2,
  ShieldAlert,
  User,
  X,
} from "lucide-react";
import { buildBackendUrl } from "@/lib/api";
import { ArtifactRenderer } from "@/components/artifacts/artifact-renderer";
import { MermaidViewer } from "@/components/artifacts/mermaid-viewer";
import { SVGViewer } from "@/components/artifacts/svg-viewer";
import { HTMLViewer } from "@/components/artifacts/html-viewer";
import type { ChatMessage, ContentBlock, SelectedSourcePage } from "@/types/events";

/**
 * Auto-link page references in chat text.
 * Matches: "page 14", "pages 13-14", "Page 24", "p.14", "p. 14", "manual page 14"
 * Works for any page number (no hardcoded range). The source viewer
 * handles missing pages gracefully.
 */
const PAGE_REF_REGEX = /\b(?:manual\s+)?(?:pages?\s*\.?\s*)(\d{1,3})(?:\s*[-\u2013]\s*(\d{1,3}))?\b/gi;

function linkifyPageRefs(
  children: React.ReactNode,
  onSelect?: (source: SelectedSourcePage) => void,
): React.ReactNode {
  if (!onSelect) return children;
  return processChildren(children, (text) => {
    const parts: React.ReactNode[] = [];
    let lastIdx = 0;
    let match: RegExpExecArray | null;
    const regex = new RegExp(PAGE_REF_REGEX.source, "gi");
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        parts.push(text.slice(lastIdx, match.index));
      }
      const startPage = parseInt(match[1], 10);
      const endPage = match[2] ? parseInt(match[2], 10) : startPage;
      const fullMatch = match[0];
      if (startPage >= 1) {
        // Build array of all pages in range
        const allPages: number[] = [];
        for (let p = startPage; p <= Math.min(endPage, startPage + 20); p++) {
          allPages.push(p);
        }
        parts.push(
          <button
            key={`pref-${match.index}`}
            type="button"
            onClick={() => onSelect({
              page: startPage,
              pages: allPages.length > 1 ? allPages : undefined,
              title: allPages.length > 1 ? `Pages ${startPage}-${endPage}` : `Page ${startPage}`,
            })}
            className="inline text-orange-500 hover:text-orange-600 underline underline-offset-2 cursor-pointer"
          >
            {fullMatch}
          </button>,
        );
      } else {
        parts.push(fullMatch);
      }
      lastIdx = regex.lastIndex;
    }
    if (lastIdx < text.length) parts.push(text.slice(lastIdx));
    return parts.length > 0 ? parts : text;
  });
}

function processChildren(
  children: React.ReactNode,
  transform: (text: string) => React.ReactNode,
): React.ReactNode {
  if (typeof children === "string") return transform(children);
  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === "string") return <span key={i}>{transform(child)}</span>;
      return child;
    });
  }
  return children;
}

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

  useEffect(() => {
    if (!lightboxSrc) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightboxSrc(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [lightboxSrc]);

  return (
    <div className={`group/msg flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
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
      <div className={`flex max-w-[75%] flex-col gap-2 ${isUser ? "items-end" : ""}`}>
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

        {/* Interleaved content blocks (text, artifacts, images in arrival order) */}
        {message.blocks && message.blocks.length > 0 ? (
          message.blocks.map((block, i) => (
            <InlineBlock
              key={i}
              block={block}
              isUser={isUser}
              onSelectSourcePage={onSelectSourcePage}
              onImageClick={setLightboxSrc}
            />
          ))
        ) : (
          /* Fallback for old messages without blocks */
          <>
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
            {message.pageImages?.map((img, idx) => (
              <PageImageBlock key={idx} img={img} onSelectSourcePage={onSelectSourcePage} onImageClick={setLightboxSrc} />
            ))}
            {message.artifacts?.map((artifact, idx) => (
              <ArtifactRenderer key={`${artifact.id}-${idx}`} artifact={artifact} onSelectSourcePage={onSelectSourcePage} />
            ))}
          </>
        )}

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

        {/* Clickable follow-up suggestions (extracted from assistant text) */}
        {!isUser && !message.isStreaming && message.content && (
          <FollowUpSuggestions text={message.content} onSelect={onQuickReply} />
        )}

        {/* Generating indicator: at the bottom, while agent is still working */}
        {message.isStreaming && (
          <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-neutral-500 py-1">
            <Loader2 className="h-4 w-4 animate-spin text-orange-400" />
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
          onClick={handleCopy}
          className="mt-1 hidden group-hover/msg:flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-gray-300 dark:text-neutral-600 hover:text-gray-500 dark:hover:text-neutral-400 transition-colors"
          title="Copy"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Artifact tag parser: extract <artifact type="..." title="...">content</artifact>
// ---------------------------------------------------------------------------

interface ParsedArtifact {
  type: string;
  title: string;
  content: string;
}

type TextSegment =
  | { kind: "text"; text: string }
  | { kind: "artifact"; artifact: ParsedArtifact }
  | { kind: "artifact_loading"; type: string; title: string };

const ARTIFACT_REGEX = /<artifact\s+type="([^"]*)"(?:\s+title="([^"]*)")?[^>]*>([\s\S]*?)<\/artifact>/g;
const ARTIFACT_OPEN_REGEX = /<artifact\s+type="([^"]*)"(?:\s+title="([^"]*)")?[^>]*>/;

function parseArtifactTags(text: string): TextSegment[] {
  const segments: TextSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  const regex = new RegExp(ARTIFACT_REGEX.source, "g");

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      const before = text.slice(lastIndex, match.index).trim();
      if (before) segments.push({ kind: "text", text: before });
    }
    segments.push({
      kind: "artifact",
      artifact: { type: match[1], title: match[2] || "", content: match[3].trim() },
    });
    lastIndex = regex.lastIndex;
  }

  // Text after last closed artifact
  if (lastIndex < text.length) {
    const remaining = text.slice(lastIndex).trim();
    if (remaining) {
      // Check if there's an unclosed <artifact ...> tag (still streaming)
      const openMatch = remaining.match(ARTIFACT_OPEN_REGEX);
      if (openMatch) {
        // Text before the open tag
        const beforeOpen = remaining.slice(0, openMatch.index).trim();
        if (beforeOpen) segments.push({ kind: "text", text: beforeOpen });
        // Show loading placeholder for the streaming artifact
        segments.push({
          kind: "artifact_loading",
          type: openMatch[1] || "",
          title: openMatch[2] || "",
        });
      } else {
        segments.push({ kind: "text", text: remaining });
      }
    }
  }

  if (segments.length === 0 && text.trim()) {
    segments.push({ kind: "text", text });
  }

  return segments;
}

// ---------------------------------------------------------------------------
// InlineBlock: renders a single content block (text, artifact, or image)
// ---------------------------------------------------------------------------

function InlineBlock({
  block,
  isUser,
  onSelectSourcePage,
  onImageClick,
}: {
  block: ContentBlock;
  isUser: boolean;
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
  onImageClick?: (src: string) => void;
}) {
  if (block.type === "text" && block.text.trim()) {
    const displayText = stripFollowupsBlock(block.text);
    if (!displayText.trim()) return null;

    // Parse <artifact> tags from the text
    const segments = parseArtifactTags(displayText);
    const hasSpecial = segments.some((s) => s.kind !== "text");

    // If no artifacts or loading placeholders, render as plain text
    if (!hasSpecial) {
      return (
        <TextBubble text={displayText} isUser={isUser} onSelectSourcePage={onSelectSourcePage} />
      );
    }

    // Mixed content: render text and artifacts interleaved
    return (
      <>
        {segments.map((seg, i) => {
          if (seg.kind === "text") {
            return <TextBubble key={i} text={seg.text} isUser={isUser} onSelectSourcePage={onSelectSourcePage} />;
          }
          if (seg.kind === "artifact_loading") {
            return (
              <div key={i} className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-900 p-6 flex items-center gap-3">
                <Loader2 className="h-5 w-5 animate-spin text-orange-400" />
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-neutral-300">
                    Generating {seg.title || seg.type || "artifact"}...
                  </div>
                  <div className="text-xs text-gray-400 dark:text-neutral-500 mt-0.5">
                    {seg.type.toUpperCase()}
                  </div>
                </div>
              </div>
            );
          }
          return (
            <InlineArtifact key={i} artifact={seg.artifact} onSelectSourcePage={onSelectSourcePage} />
          );
        })}
      </>
    );
  }

  if (block.type === "artifact") {
    return (
      <ArtifactRenderer artifact={block.data} onSelectSourcePage={onSelectSourcePage} />
    );
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
  return null;
}

// ---------------------------------------------------------------------------
// TextBubble: renders a text-only chat bubble with markdown
// ---------------------------------------------------------------------------

function TextBubble({
  text,
  isUser,
  onSelectSourcePage,
}: {
  text: string;
  isUser: boolean;
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
}) {
  // User messages: orange bubble. Assistant messages: no container, text flows naturally.
  if (isUser) {
    return (
      <div className="rounded-2xl px-4 py-3 bg-orange-500 text-white">
        <div className="chat-prose chat-prose-user">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-prose text-gray-900 dark:text-neutral-100">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              p: ({ children }) => <p>{linkifyPageRefs(children, onSelectSourcePage)}</p>,
              li: ({ children }) => <li>{linkifyPageRefs(children, onSelectSourcePage)}</li>,
              strong: ({ children }) => <strong>{linkifyPageRefs(children, onSelectSourcePage)}</strong>,
              em: ({ children }) => <em>{linkifyPageRefs(children, onSelectSourcePage)}</em>,
            }}
          >
            {text}
      </ReactMarkdown>
    </div>
  );
}

/** Renders an inline artifact (parsed from <artifact> tags in text). */
function InlineArtifact({
  artifact,
  onSelectSourcePage,
}: {
  artifact: ParsedArtifact;
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
}) {
  const { type, title, content } = artifact;
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    if (!zoomed) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setZoomed(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [zoomed]);

  const renderContent = () => {
    if (type === "mermaid") return <MermaidViewer code={content} title={title} />;
    if (type === "svg") return <SVGViewer code={content} title={title} />;
    if (type === "html" || type === "table") return <HTMLViewer code={content} title={title} />;
    return (
      <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-3">
        <div className="text-sm font-semibold text-gray-900 dark:text-neutral-100">{title}</div>
        <pre className="mt-2 overflow-x-auto rounded bg-gray-50 dark:bg-neutral-950 p-2 text-xs text-gray-700 dark:text-neutral-300">
          <code>{content.slice(0, 500)}</code>
        </pre>
      </div>
    );
  };

  return (
    <>
      {/* Inline with expand button on hover */}
      <div className="relative group/art my-2 -mx-2">
        {renderContent()}
        <button
          onClick={() => setZoomed(true)}
          className="absolute top-2 right-2 hidden group-hover/art:flex h-7 w-7 items-center justify-center rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
          title="Expand"
        >
          <Expand className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Fullscreen modal */}
      {zoomed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setZoomed(false)}
        >
          <div
            className="relative w-full max-w-6xl max-h-[94vh] flex flex-col rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl border border-gray-200 dark:border-neutral-700 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-6 py-3 shrink-0">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-neutral-100 truncate">{title}</h3>
                <p className="text-xs text-gray-400 dark:text-neutral-500 uppercase">{type}</p>
              </div>
              <button
                onClick={() => setZoomed(false)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 dark:text-neutral-500 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-auto min-h-0 bg-gray-50 dark:bg-neutral-950 [&_iframe]:!min-h-[60vh]">
              {renderContent()}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// PageImageBlock: renders a manual page image with source link
// ---------------------------------------------------------------------------

function PageImageBlock({
  img,
  onSelectSourcePage,
  onImageClick,
}: {
  img: { page: number; url: string };
  onSelectSourcePage?: (source: SelectedSourcePage) => void;
  onImageClick?: (src: string) => void;
}) {
  const url = buildBackendUrl(img.url);
  return (
    <div className="rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-2">
      <div className="mb-1 flex items-center justify-between gap-2 text-xs text-gray-400 dark:text-neutral-400">
        <span>Manual Page {img.page}</span>
        <button
          onClick={() =>
            onSelectSourcePage?.({ page: img.page, title: `Manual Page ${img.page}` })
          }
          className="inline-flex items-center gap-1 text-orange-500 hover:text-orange-600"
        >
          Open in sidebar
          <ExternalLink className="h-3 w-3" />
        </button>
      </div>
      <button type="button" onClick={() => onImageClick?.(url)} className="block">
        <img
          src={url}
          alt={`Manual page ${img.page}`}
          className="max-h-80 rounded hover:opacity-90 transition-opacity"
          loading="lazy"
        />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Follow-up extraction: parse ```followups``` code blocks from Claude's response
// This is reliable because the format is a fenced code block, not free-form text.
// ---------------------------------------------------------------------------

const FOLLOWUPS_BLOCK_REGEX = /```followups\n([\s\S]*?)```/gi;

function extractFollowUps(text: string): string[] {
  const questions: string[] = [];
  let match: RegExpExecArray | null;
  const regex = new RegExp(FOLLOWUPS_BLOCK_REGEX.source, "g");
  while ((match = regex.exec(text)) !== null) {
    const block = match[1];
    for (const line of block.split("\n")) {
      const trimmed = line.trim();
      if (trimmed.length > 5) {
        questions.push(trimmed);
      }
    }
  }
  return questions;
}

function stripFollowupsBlock(text: string): string {
  return text.replace(/```followups\n[\s\S]*?```/gi, "").trim();
}

function FollowUpSuggestions({
  text,
  onSelect,
}: {
  text: string;
  onSelect?: (message: string) => void;
}) {
  const followUps = useMemo(() => extractFollowUps(text), [text]);
  if (followUps.length === 0 || !onSelect) return null;

  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {followUps.map((q, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onSelect(q)}
          className="rounded-full border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-800 px-3 py-1.5 text-xs text-gray-600 dark:text-neutral-300 hover:border-orange-300 dark:hover:border-orange-500 hover:text-orange-600 dark:hover:text-orange-300 transition-colors text-left"
        >
          {q}
        </button>
      ))}
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
