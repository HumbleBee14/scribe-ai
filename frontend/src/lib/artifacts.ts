"use client";

import type { ArtifactEvent, ChatMessage, ContentBlock } from "@/types/events";

export interface ParsedArtifact {
  renderer: string;
  title: string;
  code: string;
}

export type ParsedTextSegment =
  | { kind: "text"; text: string }
  | { kind: "artifact"; artifact: ParsedArtifact }
  | { kind: "artifact_loading"; renderer: string; title: string; partial: string };

// Allow escaped quotes (\") inside type and title attributes
const ARTIFACT_REGEX =
  /<artifact\s+type="((?:[^"\\]|\\.)*)"(?:\s+title="((?:[^"\\]|\\.)*)")?\s*>([\s\S]*?)<\/artifact>/g;
const ARTIFACT_OPEN_REGEX = /<artifact\s+type="((?:[^"\\]|\\.)*)"(?:\s+title="((?:[^"\\]|\\.)*)")?\s*>/;

function parseArtifactMatch(match: RegExpExecArray): ParsedArtifact {
  return {
    renderer: match[1],
    // Unescape \" -> " in the title for display
    title: (match[2] || match[1]).replace(/\\"/g, '"'),
    code: match[3].trim(),
  };
}

export function parseArtifactSegments(text: string): ParsedTextSegment[] {
  const segments: ParsedTextSegment[] = [];
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
      artifact: parseArtifactMatch(match),
    });
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    const remaining = text.slice(lastIndex).trim();
    if (remaining) {
      const openMatch = remaining.match(ARTIFACT_OPEN_REGEX);
      if (openMatch) {
        const beforeOpen = remaining.slice(0, openMatch.index).trim();
        if (beforeOpen) segments.push({ kind: "text", text: beforeOpen });
        const tagEnd = (openMatch.index ?? 0) + openMatch[0].length;
        const partial = remaining.slice(tagEnd).trim();
        segments.push({
          kind: "artifact_loading",
          renderer: openMatch[1] || "",
          title: openMatch[2] || "",
          partial,
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

export function extractArtifactsFromText(
  text: string,
  idPrefix: string,
): ArtifactEvent["data"][] {
  const artifacts: ArtifactEvent["data"][] = [];
  const regex = new RegExp(ARTIFACT_REGEX.source, "g");
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const artifact = parseArtifactMatch(match);
    artifacts.push({
      id: `${idPrefix}-${match.index}`,
      renderer: artifact.renderer,
      title: artifact.title,
      code: artifact.code,
      source_pages: [],
      type: artifact.renderer,
    });
  }

  return artifacts;
}

function extractArtifactsFromBlock(
  block: ContentBlock,
  messageId: string,
  blockIndex: number,
): ArtifactEvent["data"][] {
  if (block.type === "artifact") {
    return [block.data];
  }
  if (block.type === "text") {
    return extractArtifactsFromText(block.text, `${messageId}-block-${blockIndex}`);
  }
  return [];
}

export function extractArtifactsFromMessages(
  messages: ChatMessage[],
): ArtifactEvent["data"][] {
  const deduped = new Map<string, ArtifactEvent["data"]>();

  for (const message of messages) {
    if (message.role !== "assistant") continue;

    if (message.blocks && message.blocks.length > 0) {
      message.blocks.forEach((block, blockIndex) => {
        for (const artifact of extractArtifactsFromBlock(block, message.id, blockIndex)) {
          deduped.set(artifact.id, artifact);
        }
      });
      continue;
    }

    for (const artifact of extractArtifactsFromText(message.content, message.id)) {
      deduped.set(artifact.id, artifact);
    }
  }

  return [...deduped.values()];
}
