"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Trash2 } from "lucide-react";
import { useChat } from "@/lib/use-chat";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { WelcomeScreen } from "@/components/chat/welcome-screen";
import { SessionSidebar } from "@/components/evidence/session-sidebar";
import { SourceViewer } from "@/components/evidence/source-viewer";
import type { SelectedSourcePage } from "@/types/events";

export default function Home() {
  const { messages, isStreaming, session, sendMessage, stopStreaming, clearMessages } =
    useChat();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [selectedSource, setSelectedSource] = useState<SelectedSourcePage | null>(
    null
  );

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (
    text: string,
    images?: Array<{ mediaType: string; data: string }>
  ) => {
    sendMessage(text, images);
  };

  const artifacts = useMemo(
    () => messages.flatMap((message) => message.artifacts ?? []),
    [messages]
  );

  return (
    <div className="flex h-screen">
      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-neutral-800 bg-neutral-950 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="text-lg">&#x1F525;</span>
            <div>
              <h1 className="text-sm font-semibold text-white">
                Vulcan OmniPro 220 Expert
              </h1>
              <p className="text-xs text-neutral-500">
                Multimodal welding assistant
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => {
                clearMessages();
                setSelectedSource(null);
              }}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear
            </button>
          )}
        </header>

        {/* Messages or welcome */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onQuickAction={(msg) => handleSend(msg)} />
          ) : (
            <div className="space-y-6 px-6 py-4">
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onQuickReply={handleSend}
                  onSelectSourcePage={setSelectedSource}
                />
              ))}
              <div ref={scrollRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          onStop={stopStreaming}
          isStreaming={isStreaming}
          disabled={isStreaming}
        />
      </div>

      {/* Right sidebar (session context + future artifact panel) */}
      <aside className="hidden w-72 shrink-0 border-l border-neutral-800 bg-neutral-950 p-4 lg:block">
        <SessionSidebar session={session} />
        <SourceViewer selectedSource={selectedSource} artifacts={artifacts} />
      </aside>
    </div>
  );
}
