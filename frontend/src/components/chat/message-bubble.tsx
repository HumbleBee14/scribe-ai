"use client";

import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  Bot,
  Loader2,
  Search,
  ShieldAlert,
  User,
} from "lucide-react";
import type { ChatMessage } from "@/types/events";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-orange-600" : "bg-neutral-700"
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
        {/* Safety warnings */}
        {message.safetyWarnings?.map((warning, i) => (
          <div
            key={i}
            className={`flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${
              warning.level === "danger"
                ? "bg-red-950 border border-red-800 text-red-200"
                : "bg-yellow-950 border border-yellow-800 text-yellow-200"
            }`}
          >
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{warning.content}</span>
          </div>
        ))}

        {/* Tool call badges */}
        {message.toolCalls?.map((tc, i) => (
          <div
            key={i}
            className="flex items-center gap-2 text-xs text-neutral-400"
          >
            {tc.ok === undefined ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Search className="h-3 w-3" />
            )}
            <span>{tc.label}</span>
          </div>
        ))}

        {/* Main text */}
        {message.content && (
          <div
            className={`rounded-2xl px-4 py-3 ${
              isUser
                ? "bg-orange-600 text-white"
                : "bg-neutral-800 text-neutral-100"
            }`}
          >
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Page images */}
        {message.pageImages?.map((img, i) => (
          <div
            key={i}
            className="rounded-lg border border-neutral-700 bg-neutral-900 p-2"
          >
            <div className="text-xs text-neutral-400 mb-1">
              Manual Page {img.page}
            </div>
            <img
              src={`http://localhost:8000${img.url}`}
              alt={`Manual page ${img.page}`}
              className="max-h-80 rounded"
              loading="lazy"
            />
          </div>
        ))}

        {/* Clarification card */}
        {message.clarification && (
          <div className="rounded-lg border border-blue-800 bg-blue-950 p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-blue-400 shrink-0" />
              <div>
                <p className="text-sm text-blue-200">
                  {message.clarification.question}
                </p>
                {message.clarification.options && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {message.clarification.options.map((opt, i) => (
                      <button
                        key={i}
                        className="rounded-full bg-blue-900 px-3 py-1 text-xs text-blue-200 hover:bg-blue-800 transition-colors"
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
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking...
          </div>
        )}
      </div>
    </div>
  );
}
