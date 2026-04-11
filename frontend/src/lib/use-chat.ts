"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat } from "./api";
import { getMessageStorageKey, listConversations, saveConversation } from "./history";
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

function loadMessages(productId: string, conversationId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(getMessageStorageKey(productId, conversationId));
    if (!raw) return [];
    const messages = JSON.parse(raw) as ChatMessage[];
    // Clean up: ensure no message is stuck in streaming state,
    // and auto-close unclosed <artifact> tags from interrupted responses
    return messages.map((m) => ({
      ...m,
      isStreaming: false,
      content: m.content?.replace(
        /(<artifact\s+[^>]*>)((?![\s\S]*<\/artifact>)[\s\S]*)$/g,
        "$1$2</artifact>"
      ) ?? "",
    }));
  } catch {
    return [];
  }
}

const MAX_STORED_BYTES = 512 * 1024; // 512KB per conversation

function persistMessages(productId: string, conversationId: string, messages: ChatMessage[]): void {
  // Strip only uploaded image base64 (user-uploaded photos, too large)
  // Everything else — artifacts, pageImages (URLs not base64), safetyWarnings — is kept
  const cleaned = messages.map((m) => ({
    ...m,
    images: m.images?.map((img) => ({ ...img, data: "" })), // strip upload base64 only
    isStreaming: false,
  }));

  const json = JSON.stringify(cleaned);

  // If over size limit, keep only the last 20 messages to stay under quota
  if (json.length > MAX_STORED_BYTES) {
    const trimmed = cleaned.slice(-20);
    const trimmedJson = JSON.stringify(trimmed);
    try {
      localStorage.setItem(getMessageStorageKey(productId, conversationId), trimmedJson);
    } catch (e) {
      console.warn("[useChat] Could not persist messages:", e);
    }
    return;
  }

  try {
    localStorage.setItem(getMessageStorageKey(productId, conversationId), json);
  } catch (e) {
    console.warn("[useChat] Could not persist messages (storage full?):", e);
    // Try trimming to last 10 messages as fallback
    try {
      localStorage.setItem(
        getMessageStorageKey(productId, conversationId),
        JSON.stringify(cleaned.slice(-10))
      );
    } catch {
      // Give up
    }
  }
}

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

export function useChat(productId: string, conversationId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    loadMessages(productId, conversationId)
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [session, setSession] = useState<SessionState | null>(null);
  const sessionIdRef = useRef<string>(conversationId);
  const abortRef = useRef<AbortController | null>(null);

  // When conversationId changes (history navigation), reload messages
  useEffect(() => {
    const loaded = loadMessages(productId, conversationId);
    setMessages(loaded);
    prevCountRef.current = loaded.length; // Don't treat loaded messages as "new"
    sessionIdRef.current = conversationId;
    setSession(null);
  }, [conversationId, productId]);

  // Track message count to detect actual new messages vs. loading from storage
  const prevCountRef = useRef<number>(0);

  // Persist messages to localStorage on every change (debounced)
  const persistRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (messages.length === 0) return;
    if (persistRef.current) clearTimeout(persistRef.current);
    persistRef.current = setTimeout(() => {
      persistMessages(productId, conversationId, messages);

      // Only update conversation summary when message count actually increased
      // (not when loading from storage on conversation switch)
      const isNewMessage = messages.length > prevCountRef.current;
      prevCountRef.current = messages.length;

      if (isNewMessage) {
        const firstUser = messages.find((m) => m.role === "user");
        if (firstUser) {
          // Preserve existing createdAt if conversation already exists
          const existing = listConversations(productId).find((c) => c.id === conversationId);
          saveConversation(productId, {
            id: conversationId,
            productId,
            title: firstUser.content.slice(0, 60) || "Image conversation",
            createdAt: existing?.createdAt ?? Date.now(),
            updatedAt: Date.now(),
            messageCount: messages.length,
          });
        }
      }
    }, 500);
    return () => {
      if (persistRef.current) clearTimeout(persistRef.current);
    };
  }, [messages, conversationId, productId]);

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
          session_id: sessionIdRef.current,
          product_id: productId,
          message: text,
          images: images?.map((img) => ({
            media_type: img.mediaType,
            data: img.data,
          })),
        };

        for await (const { event, data } of streamChat(payload, controller.signal)) {
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
                  // Append to last text block, or create one
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
                  // Resolve any tool calls still spinning (tool_end may not have arrived)
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

        // Ensure streaming is cleared after the stream ends
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
  }, []);

  return { messages, isStreaming, session, sendMessage, stopStreaming, clearMessages };
}
