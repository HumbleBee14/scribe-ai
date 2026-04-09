"use client";

import { useCallback, useRef, useState } from "react";
import { streamChat } from "./api";
import type {
  ArtifactEvent,
  ChatMessage,
  ImageEvent,
  SafetyWarningEvent,
  SessionState,
} from "@/types/events";

let messageCounter = 0;
function nextId(): string {
  return `msg-${++messageCounter}-${Date.now()}`;
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [session, setSession] = useState<SessionState | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const sendMessage = useCallback(
    async (
      text: string,
      images?: Array<{ mediaType: string; data: string }>
    ) => {
      if (!text.trim() && !images?.length) return;

      // Initialize session ID on first message
      if (!sessionIdRef.current) {
        sessionIdRef.current = crypto.randomUUID();
      }

      // Add user message
      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content: text,
        images,
      };

      // Prepare assistant message placeholder
      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: "assistant",
        content: "",
        toolCalls: [],
        artifacts: [],
        pageImages: [],
        safetyWarnings: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      try {
        const payload = {
          session_id: sessionIdRef.current,
          message: text,
          images: images?.map((img) => ({
            media_type: img.mediaType,
            data: img.data,
          })),
        };

        for await (const { event, data } of streamChat(payload)) {
          setMessages((prev) => {
            const updated = [...prev];
            const last = { ...updated[updated.length - 1] };

            switch (event) {
              case "text_delta":
                last.content += (data as { content: string }).content;
                break;

              case "tool_start":
                last.toolCalls = [
                  ...(last.toolCalls ?? []),
                  {
                    tool: data.tool as string,
                    label: data.label as string,
                  },
                ];
                break;

              case "tool_end": {
                const tc = last.toolCalls ?? [];
                const idx = tc.findIndex(
                  (t) => t.tool === (data.tool as string) && t.ok === undefined
                );
                if (idx >= 0) {
                  const copy = [...tc];
                  copy[idx] = { ...copy[idx], ok: data.ok as boolean };
                  last.toolCalls = copy;
                }
                break;
              }

              case "artifact":
                last.artifacts = [
                  ...(last.artifacts ?? []),
                  data as ArtifactEvent["data"],
                ];
                break;

              case "image":
                last.pageImages = [
                  ...(last.pageImages ?? []),
                  data as ImageEvent["data"],
                ];
                break;

              case "safety_warning":
                last.safetyWarnings = [
                  ...(last.safetyWarnings ?? []),
                  data as SafetyWarningEvent["data"],
                ];
                break;

              case "clarification":
                last.clarification = data as {
                  question: string;
                  options?: string[];
                };
                break;

              case "session_update":
                setSession({
                  id: data.id as string,
                  currentProcess: data.current_process as string | null,
                  currentVoltage: data.current_voltage as string | null,
                  currentMaterial: data.current_material as string | null,
                  currentThickness: data.current_thickness as string | null,
                  setupStepsCompleted:
                    (data.setup_steps_completed as string[]) ?? [],
                  contextSummary: (data.context_summary as string) ?? "",
                });
                break;

              case "done":
                last.isStreaming = false;
                break;

              case "error":
                last.content += `\n\n**Error:** ${data.message as string}`;
                last.isStreaming = false;
                break;
            }

            updated[updated.length - 1] = last;
            return updated;
          });
        }
      } catch (err) {
        setMessages((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          last.content += `\n\n**Connection error:** ${err instanceof Error ? err.message : "Unknown error"}`;
          last.isStreaming = false;
          updated[updated.length - 1] = last;
          return updated;
        });
      } finally {
        setIsStreaming(false);
      }
    },
    []
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    sessionIdRef.current = null;
    setSession(null);
  }, []);

  return { messages, isStreaming, session, sendMessage, clearMessages };
}
