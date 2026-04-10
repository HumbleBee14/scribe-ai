"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, LibraryBig, Loader2, PanelLeftOpen } from "lucide-react";
import { fetchProducts, getProductIngestionStatus, ProductSummary } from "@/lib/api";
import { listConversations } from "@/lib/history";
import { useChat } from "@/lib/use-chat";
import { extractArtifactsFromMessages } from "@/lib/artifacts";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { WelcomeScreen } from "@/components/chat/welcome-screen";
import { SessionSidebar } from "@/components/evidence/session-sidebar";
import { SourceViewer } from "@/components/evidence/source-viewer";
import { HistorySidebar } from "@/components/layout/history-sidebar";
import { MobileContextPanel } from "@/components/layout/mobile-context-panel";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { ProductManualManager } from "@/components/products/product-manual-manager";
import type { SelectedSourcePage } from "@/types/events";

interface Props {
  initialProductId: string;
}

export function ProductWorkspace({ initialProductId }: Props) {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [activeProductId, setActiveProductId] = useState(initialProductId);
  const [conversationId, setConversationId] = useState<string>(() => crypto.randomUUID());
  const [selectedSource, setSelectedSource] = useState<SelectedSourcePage | null>(null);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [mobileContextOpen, setMobileContextOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeProduct = useMemo(
    () => products.find((product) => product.id === activeProductId) ?? null,
    [products, activeProductId]
  );

  const { messages, isStreaming, session, sendMessage, stopStreaming, clearMessages } =
    useChat(activeProductId, conversationId);

  const artifacts = useMemo(() => extractArtifactsFromMessages(messages), [messages]);

  const loadProducts = useCallback(async () => {
    const data = await fetchProducts();
    setProducts(data.products);
    setActiveProductId((current) => {
      if (data.products.some((product) => product.id === current)) return current;
      return data.default_product_id;
    });
  }, []);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    setActiveProductId(initialProductId);
  }, [initialProductId]);

  useEffect(() => {
    if (!activeProduct) return;
    const existing = listConversations(activeProduct.id)[0];
    setSelectedSource(null);
    setConversationId(existing?.id ?? crypto.randomUUID());
  }, [activeProduct]);

  useEffect(() => {
    if (!activeProduct) return;
    if (!["processing", "draft"].includes(activeProduct.ingestion.status)) return;
    const interval = window.setInterval(async () => {
      try {
        const status = await getProductIngestionStatus(activeProduct.id);
        setProducts((prev) =>
          prev.map((product) =>
            product.id === activeProduct.id
              ? {
                  ...product,
                  status: status.status,
                  ingestion: status,
                }
              : product
          )
        );
      } catch {
        // Keep last known state.
      }
    }, 2500);
    return () => window.clearInterval(interval);
  }, [activeProduct]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: messages.length > 1 ? "smooth" : "auto" });
  }, [messages]);

  const handleSend = useCallback(
    (text: string, images?: Array<{ mediaType: string; data: string }>) => {
      sendMessage(text, images);
    },
    [sendMessage]
  );

  const handleNew = useCallback(() => {
    clearMessages();
    setSelectedSource(null);
    setConversationId(crypto.randomUUID());
  }, [clearMessages]);

  const handleSelectHistory = useCallback(
    (id: string) => {
      if (id === conversationId) return;
      setSelectedSource(null);
      setConversationId(id);
    },
    [conversationId]
  );

  const chatDisabled =
    isStreaming || !activeProduct || activeProduct.ingestion.status !== "ready";

  if (!activeProduct) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-neutral-950">
        <div className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-neutral-400">
          <Loader2 suppressHydrationWarning className="h-4 w-4 animate-spin" />
          Loading product workspace...
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-neutral-950">
      {historyOpen && (
        <HistorySidebar
          productId={activeProduct.id}
          activeId={conversationId}
          onSelect={handleSelectHistory}
          onNew={handleNew}
          onCollapse={() => setHistoryOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-5 py-3 dark:border-neutral-700 dark:bg-neutral-900 shrink-0">
          <div className="flex items-center gap-3">
            {!historyOpen && (
              <button
                onClick={() => setHistoryOpen(true)}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 transition-colors hover:text-gray-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-100"
                title="Show history"
              >
                <PanelLeftOpen suppressHydrationWarning className="h-4 w-4" />
              </button>
            )}
            <Link
              href="/"
              className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs text-gray-600 dark:border-neutral-700 dark:text-neutral-300"
            >
              <ArrowLeft suppressHydrationWarning className="h-3.5 w-3.5" />
              Products
            </Link>
            <div>
              <h1 className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
                {activeProduct.name}
              </h1>
              <p className="text-xs text-gray-400 dark:text-neutral-500">
                {activeProduct.description || "Local-first multimodal manual assistant"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={activeProductId}
              onChange={(event) => {
                const nextProductId = event.target.value;
                window.location.href = `/products/${nextProductId}`;
              }}
              className="h-8 rounded-lg border border-gray-200 bg-white px-2 text-xs text-gray-700 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200"
            >
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setMobileContextOpen(true)}
              className="flex h-8 items-center gap-2 rounded-lg border border-gray-200 bg-white px-2.5 text-xs text-gray-600 transition-colors hover:text-gray-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:text-white lg:hidden"
              title="Open context, sources, and artifacts"
            >
              <LibraryBig suppressHydrationWarning className="h-4 w-4" />
              Context
            </button>
            <ThemeToggle />
          </div>
        </header>

        {activeProduct.ingestion.status !== "ready" && (
          <div className="border-b border-orange-200 bg-orange-50 px-5 py-2 text-xs text-orange-700 dark:border-orange-900/40 dark:bg-orange-950/30 dark:text-orange-200">
            {activeProduct.ingestion.status === "processing" ? (
              <span className="inline-flex items-center gap-2">
                <Loader2 suppressHydrationWarning className="h-3.5 w-3.5 animate-spin" />
                {activeProduct.ingestion.message || "Manual ingestion is running in the background."}
              </span>
            ) : (
              activeProduct.ingestion.message ||
              "Upload one or more documents, then start chatting once ingestion is ready."
            )}
          </div>
        )}

        <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex min-h-0 flex-col">
            <div className="flex-1 overflow-y-auto">
              {messages.length === 0 ? (
                <div className="flex min-h-full flex-col">
                  <ProductManualManager
                    product={activeProduct}
                    onProductChange={(next) =>
                      setProducts((prev) =>
                        prev.map((product) => (product.id === next.id ? next : product))
                      )
                    }
                  />
                  <div className="flex flex-1">
                    <WelcomeScreen
                      productName={activeProduct.name}
                      productDescription={
                        activeProduct.description || "Choose a product and ask grounded questions."
                      }
                      quickActions={activeProduct.quick_actions}
                      onQuickAction={(msg) => handleSend(msg)}
                    />
                  </div>
                </div>
              ) : (
                <div className="mx-auto max-w-6xl space-y-6 px-6 py-4">
                  <ProductManualManager
                    product={activeProduct}
                    onProductChange={(next) =>
                      setProducts((prev) =>
                        prev.map((product) => (product.id === next.id ? next : product))
                      )
                    }
                  />
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

            <div className="border-t border-gray-200 bg-white dark:border-neutral-700 dark:bg-neutral-900">
              <div className="mx-auto max-w-6xl">
                <ChatInput
                  onSend={handleSend}
                  onStop={stopStreaming}
                  isStreaming={isStreaming}
                  disabled={chatDisabled}
                />
              </div>
            </div>
          </div>

          <aside className="hidden border-l border-gray-200 bg-white dark:border-neutral-700 dark:bg-neutral-900 xl:flex xl:flex-col">
            <div className="flex-1 space-y-6 overflow-y-auto p-4">
              <SessionSidebar session={session} />
              <SourceViewer
                productId={activeProduct.id}
                selectedSource={selectedSource}
                artifacts={artifacts}
              />
            </div>
          </aside>
        </div>
      </div>

      <MobileContextPanel
        open={mobileContextOpen}
        onClose={() => setMobileContextOpen(false)}
        productId={activeProduct.id}
        session={session}
        selectedSource={selectedSource}
        artifacts={artifacts}
      />
    </div>
  );
}
