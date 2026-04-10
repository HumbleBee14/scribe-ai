"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useChat } from "@/lib/use-chat";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { WelcomeScreen } from "@/components/chat/welcome-screen";
import { SessionSidebar } from "@/components/evidence/session-sidebar";
import { SourceViewer } from "@/components/evidence/source-viewer";
import { HistorySidebar } from "@/components/layout/history-sidebar";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import type { SelectedSourcePage } from "@/types/events";

export default function Home() {
  const [conversationId, setConversationId] = useState<string>(() => crypto.randomUUID());
  const [selectedSource, setSelectedSource] = useState<SelectedSourcePage | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // useChat now owns persistence and restoration keyed by conversationId
  const { messages, isStreaming, session, sendMessage, stopStreaming, clearMessages } =
    useChat(conversationId);

  const handleSend = (text: string, images?: Array<{ mediaType: string; data: string }>) => {
    sendMessage(text, images);
    // Scroll after a short delay so the new message is rendered
    setTimeout(() => scrollRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const handleNew = useCallback(() => {
    clearMessages();
    setSelectedSource(null);
    setConversationId(crypto.randomUUID());
  }, [clearMessages]);

  const handleSelectHistory = useCallback(
    (id: string) => {
      if (id === conversationId) return;
      setSelectedSource(null);
      setConversationId(id); // useChat will reload messages for this id
    },
    [conversationId]
  );

  const artifacts = useMemo(
    () => messages.flatMap((m) => m.artifacts ?? []),
    [messages]
  );

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-neutral-950">
      {/* Left: History sidebar */}
      <HistorySidebar
        activeId={conversationId}
        onSelect={handleSelectHistory}
        onNew={handleNew}
      />

      {/* Center: Chat */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 px-5 py-3 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-lg">&#x1F525;</span>
            <div>
              <h1 className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
                Vulcan OmniPro 220 Expert
              </h1>
              <p className="text-xs text-gray-400 dark:text-neutral-500">
                Multimodal welding assistant
              </p>
            </div>
          </div>
          <ThemeToggle />
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <WelcomeScreen onQuickAction={(msg) => handleSend(msg)} />
          ) : (
            <div className="space-y-6 px-6 py-4 max-w-3xl mx-auto">
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
        <div className="border-t border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900">
          <div className="max-w-3xl mx-auto">
            <ChatInput
              onSend={handleSend}
              onStop={stopStreaming}
              isStreaming={isStreaming}
              disabled={isStreaming}
            />
          </div>
        </div>
      </div>

      {/* Right: Context sidebar */}
      <aside className="hidden w-72 shrink-0 border-l border-gray-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 lg:flex flex-col">
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          <SessionSidebar session={session} />
          <SourceViewer selectedSource={selectedSource} artifacts={artifacts} />
        </div>
      </aside>
    </div>
  );
}
