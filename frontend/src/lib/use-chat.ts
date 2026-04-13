"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getConversation, streamChat } from "./api";
import type {
  ArtifactEvent,
  ChatMessage,
  ErrorEvent,
  ImageEvent,
  SafetyWarningEvent,
  SessionState,
  SessionUpdateEvent,
} from "@/types/events";

let messageCounter = 0;
function nextId(): string {
  return `msg-${++messageCounter}-${Date.now()}`;
}

const REQUEST_TIMEOUT_MS = 90_000; // 90 seconds

/** Mark all pending tool calls (ok === undefined) as completed. */
function resolvePendingToolCalls(msg: ChatMessage): ChatMessage {
  if (!msg.toolCalls?.some((t) => t.ok === undefined)) return msg;
  return {
    ...msg,
    toolCalls: msg.toolCalls.map((t) =>
      t.ok === undefined ? { ...t, ok: true } : t
    ),
  };
}

/** Convert a DB message row to a ChatMessage for rendering. */
function dbMessageToChatMessage(row: { id: number; role: string; content: Record<string, unknown> }): ChatMessage {
  const content = row.content;
  // New format: blocks array preserving interleaved text/image/artifact positions
  const blocks = content.blocks as Array<{ type: string; text?: string; data?: Record<string, unknown> }> | undefined;

  // Build full text content from text blocks (for follow-up extraction, search, etc.)
  const textContent = blocks
    ? blocks.filter((b) => b.type === "text").map((b) => b.text || "").join("")
    : (content.text as string) || "";

  const msg: ChatMessage = {
    id: `db-${row.id}`,
    role: row.role as "user" | "assistant",
    content: textContent,
    isStreaming: false,
  };

  if (row.role === "assistant") {
    if (content.toolCalls) msg.toolCalls = content.toolCalls as ChatMessage["toolCalls"];

    if (blocks) {
      // Blocks format: use directly, preserving interleaved positions
      msg.blocks = blocks.map((b) => {
        if (b.type === "text") return { type: "text" as const, text: b.text || "" };
        if (b.type === "image") return { type: "image" as const, data: b.data as ImageEvent["data"] };
        if (b.type === "artifact") return { type: "artifact" as const, data: b.data as ArtifactEvent["data"] };
        return { type: "text" as const, text: "" };
      });
      // Extract pageImages from image blocks for sidebar source viewer
      msg.pageImages = blocks
        .filter((b) => b.type === "image")
        .map((b) => b.data as ImageEvent["data"]);
    } else {
      // Legacy flat format (old messages before blocks migration)
      if (content.sourcePages) msg.pageImages = content.sourcePages as ChatMessage["pageImages"];
      if (content.text) msg.content = content.text as string;
    }
  }

  if (row.role === "user" && content.images) {
    msg.uploadedImagePaths = content.images as string[];
  }

  return msg;
}

export function useChat(productId: string, conversationId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [session, setSession] = useState<SessionState | null>(null);
  // Use ref to avoid re-render loops between useChat and workspace
  const activeConvRef = useRef<string | null>(conversationId);
  const [newConversationId, setNewConversationId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Load messages from DB when conversationId changes
  useEffect(() => {
    activeConvRef.current = conversationId;
    setNewConversationId(null);
    setSession(null);

    if (!conversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    getConversation(conversationId)
      .then((conv) => {
        if (cancelled || !conv) return;
        setMessages(conv.messages.map(dbMessageToChatMessage));
      })
      .catch(() => {
        if (cancelled) return;
        setMessages([{
          id: "error-load",
          role: "assistant",
          content: "Could not load this conversation. The backend may be unreachable.",
          isStreaming: false,
        }]);
      });
    return () => { cancelled = true; };
  }, [conversationId]);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(
    async (
      text: string,
      images?: Array<{ mediaType: string; data: string }>
    ) => {
      if (!text.trim() && !images?.length) return;

      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content: text,
        images,
      };

      const assistantId = nextId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        toolCalls: [],
        pageImages: [],
        safetyWarnings: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;
      const timeout = setTimeout(() => controller.abort("timeout"), REQUEST_TIMEOUT_MS);

      try {
        const payload = {
          conversation_id: activeConvRef.current || undefined,
          product_id: productId,
          message: text,
          images: images?.map((img) => ({
            media_type: img.mediaType,
            data: img.data,
          })),
        };

        for await (const { event, data } of streamChat(payload, controller.signal)) {
          // Handle new conversation creation from backend
          if (event === "conversation_created") {
            const newId = (data as { conversation_id: string }).conversation_id;
            activeConvRef.current = newId;
            setNewConversationId(newId);
            continue;
          }

          if (event === "session_update") {
            const sessionData = data as SessionUpdateEvent["data"];
            setSession({
              id: sessionData.id,
              productId: sessionData.product_id,
              productName: sessionData.product_name,
              currentProcess: sessionData.current_process,
              currentVoltage: sessionData.current_voltage,
              currentMaterial: sessionData.current_material,
              currentThickness: sessionData.current_thickness,
              setupStepsCompleted: sessionData.setup_steps_completed ?? [],
              safetyWarningsShown: sessionData.safety_warnings_shown ?? [],
              contextSummary: sessionData.context_summary ?? "",
            });
            continue;
          }

          setMessages((prev) =>
            prev.map((message) => {
              if (message.id !== assistantId) return message;
              const msg: ChatMessage = { ...message };

              switch (event) {
                case "text_delta": {
                  const chunk = (data as { content: string }).content;
                  msg.content += chunk;
                  const blocks = [...(msg.blocks ?? [])];
                  const lastBlock = blocks[blocks.length - 1];
                  if (lastBlock && lastBlock.type === "text") {
                    blocks[blocks.length - 1] = { type: "text", text: lastBlock.text + chunk };
                  } else {
                    blocks.push({ type: "text", text: chunk });
                  }
                  msg.blocks = blocks;
                  break;
                }

                case "tool_start":
                  msg.toolCalls = [
                    ...(msg.toolCalls ?? []),
                    { tool: data.tool as string, label: data.label as string },
                  ];
                  break;

                case "tool_end": {
                  const calls = msg.toolCalls ?? [];
                  const idx = calls.findIndex(
                    (t) => t.tool === (data.tool as string) && t.ok === undefined
                  );
                  if (idx >= 0) {
                    const copy = [...calls];
                    copy[idx] = { ...copy[idx], ok: data.ok as boolean };
                    msg.toolCalls = copy;
                  }
                  break;
                }

                case "artifact": {
                  const artifactData = data as ArtifactEvent["data"];
                  msg.blocks = [...(msg.blocks ?? []), { type: "artifact", data: artifactData }];
                  break;
                }

                case "image": {
                  const imgData = data as ImageEvent["data"];
                  msg.pageImages = [...(msg.pageImages ?? []), imgData];
                  msg.blocks = [...(msg.blocks ?? []), { type: "image", data: imgData }];
                  break;
                }

                case "safety_warning":
                  msg.safetyWarnings = [
                    ...(msg.safetyWarnings ?? []),
                    data as SafetyWarningEvent["data"],
                  ];
                  break;

                case "clarification":
                  msg.clarification = data as { question: string; options?: string[] };
                  break;

                case "done":
                  msg.isStreaming = false;
                  msg.toolCalls = (msg.toolCalls ?? []).map((t) =>
                    t.ok === undefined ? { ...t, ok: true } : t
                  );
                  break;

                case "error":
                  msg.content += `\n\n**Error:** ${(data as ErrorEvent["data"]).message}`;
                  msg.isStreaming = false;
                  msg.toolCalls = (msg.toolCalls ?? []).map((t) =>
                    t.ok === undefined ? { ...t, ok: false } : t
                  );
                  break;
              }

              return msg;
            })
          );
        }

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? resolvePendingToolCalls({ ...m, isStreaming: false }) : m
          )
        );
      } catch (err) {
        const isAbort = err instanceof DOMException && err.name === "AbortError";
        const msg = isAbort
          ? controller.signal.reason === "timeout"
            ? "Request timed out after 90 seconds."
            : "Stopped."
          : `Connection error: ${err instanceof Error ? err.message : "Unknown error"}`;

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? resolvePendingToolCalls({
                  ...m,
                  content: m.content
                    ? m.content + (isAbort && msg === "Stopped." ? "" : `\n\n*${msg}*`)
                    : `*${msg}*`,
                  isStreaming: false,
                })
              : m
          )
        );
      } finally {
        clearTimeout(timeout);
        abortRef.current = null;
        setIsStreaming(false);
      }
    },
    [productId]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setSession(null);
    activeConvRef.current = null;
    setNewConversationId(null);
  }, []);

  return {
    messages,
    isStreaming,
    session,
    newConversationId,
    sendMessage,
    stopStreaming,
    clearMessages,
  };
}
