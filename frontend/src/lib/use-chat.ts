"use client";

import { useCallback, useRef, useState } from "react";
import { streamChat } from "./api";
import type {
  ArtifactEvent,
  ChatMessage,
  DoneEvent,
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
      const assistantId = nextId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
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
          if (event === "session_update") {
            const sessionData = data as SessionUpdateEvent["data"];
            setSession({
              id: sessionData.id,
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

              const nextMessage: ChatMessage = { ...message };

              switch (event) {
                case "text_delta":
                  nextMessage.content += (data as { content: string }).content;
                  break;

                case "tool_start":
                  nextMessage.toolCalls = [
                    ...(nextMessage.toolCalls ?? []),
                    {
                      tool: data.tool as string,
                      label: data.label as string,
                    },
                  ];
                  break;

                case "tool_end": {
                  const toolCalls = nextMessage.toolCalls ?? [];
                  const idx = toolCalls.findIndex(
                    (t) => t.tool === (data.tool as string) && t.ok === undefined
                  );
                  if (idx >= 0) {
                    const copy = [...toolCalls];
                    copy[idx] = { ...copy[idx], ok: data.ok as boolean };
                    nextMessage.toolCalls = copy;
                  }
                  break;
                }

                case "artifact":
                  nextMessage.artifacts = [
                    ...(nextMessage.artifacts ?? []),
                    data as ArtifactEvent["data"],
                  ];
                  break;

                case "image":
                  nextMessage.pageImages = [
                    ...(nextMessage.pageImages ?? []),
                    data as ImageEvent["data"],
                  ];
                  break;

                case "safety_warning":
                  nextMessage.safetyWarnings = [
                    ...(nextMessage.safetyWarnings ?? []),
                    data as SafetyWarningEvent["data"],
                  ];
                  break;

                case "clarification":
                  nextMessage.clarification = data as {
                    question: string;
                    options?: string[];
                  };
                  break;

                case "done":
                  nextMessage.isStreaming = false;
                  break;

                case "error":
                  nextMessage.content += `\n\n**Error:** ${(data as ErrorEvent["data"]).message}`;
                  nextMessage.isStreaming = false;
                  break;
              }

              return nextMessage;
            })
          );

          if (event === "done") {
            const doneData = data as DoneEvent["data"];
            if (doneData.status === "clarification_required") {
              setIsStreaming(false);
            }
          }
        }

        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId ? { ...message, isStreaming: false } : message
          )
        );
      } catch (err) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content:
                    message.content +
                    `\n\n**Connection error:** ${
                      err instanceof Error ? err.message : "Unknown error"
                    }`,
                  isStreaming: false,
                }
              : message
          )
        );
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
