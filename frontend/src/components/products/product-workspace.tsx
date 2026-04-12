"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Home, LibraryBig, Loader2, PanelLeftOpen, RefreshCw } from "lucide-react";
import {
  BACKEND_URL,
  buildBackendUrl,
  fetchProducts,
  getProductIngestionStatus,
  ProductSummary,
} from "@/lib/api";
import { listConversations } from "@/lib/history";
import { useChat } from "@/lib/use-chat";
import { extractArtifactsFromMessages } from "@/lib/artifacts";
import { ChatInput } from "@/components/chat/chat-input";
import { MessageBubble } from "@/components/chat/message-bubble";
import { WelcomeScreen } from "@/components/chat/welcome-screen";
import { SourceViewer } from "@/components/evidence/source-viewer";
import { HistorySidebar } from "@/components/layout/history-sidebar";
import { MobileContextPanel } from "@/components/layout/mobile-context-panel";
import { ThemeToggle } from "@/components/layout/theme-toggle";
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
  const [productsLoadError, setProductsLoadError] = useState<string | null>(null);
  const [productsLoading, setProductsLoading] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeProduct = useMemo(
    () => products.find((product) => product.id === activeProductId) ?? null,
    [products, activeProductId]
  );

  const { messages, isStreaming, sendMessage, stopStreaming, clearMessages } =
    useChat(activeProductId, conversationId);

  const artifacts = useMemo(() => extractArtifactsFromMessages(messages), [messages]);

  const loadProducts = useCallback(async () => {
    setProductsLoading(true);
    setProductsLoadError(null);
    try {
      const data = await fetchProducts();
      setProducts(data.products);
      setActiveProductId((current) => {
        if (data.products.some((product) => product.id === current)) return current;
        return data.default_product_id;
      });
    } catch (e) {
      const msg =
        e instanceof TypeError && e.message === "Failed to fetch"
          ? `Could not reach the API at ${BACKEND_URL}. Start the backend or set NEXT_PUBLIC_BACKEND_URL.`
          : e instanceof Error
            ? e.message
            : "Could not load products.";
      setProductsLoadError(msg);
    } finally {
      setProductsLoading(false);
    }
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

  const [refreshing, setRefreshing] = useState(false);
  const refreshStatus = useCallback(async () => {
    setRefreshing(true);
    try {
      await loadProducts();
    } finally {
      setRefreshing(false);
    }
  }, [loadProducts]);

  // Track whether all docs are processed for the current product.
  // Resets on product switch; once true, stays true (no more checks).
  const [docsReady, setDocsReady] = useState(false);
  const [processingWarning, setProcessingWarning] = useState(false);

  useEffect(() => {
    if (!activeProduct) return;
    const ready = activeProduct.ingestion.status === "ready";
    setDocsReady(ready);
    setProcessingWarning(false);
  }, [activeProduct?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync docsReady when product data refreshes (e.g. after manual refresh)
  useEffect(() => {
    if (activeProduct?.ingestion.status === "ready") {
      setDocsReady(true);
    }
  }, [activeProduct?.ingestion.status]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: messages.length > 1 ? "smooth" : "auto" });
  }, [messages]);

  // Auto-dismiss warning after 5 seconds
  useEffect(() => {
    if (!processingWarning) return;
    const timer = setTimeout(() => setProcessingWarning(false), 5000);
    return () => clearTimeout(timer);
  }, [processingWarning]);

  const handleSend = useCallback(
    async (text: string, images?: Array<{ mediaType: string; data: string }>) => {
      // If docs not ready, check once before sending
      if (!docsReady) {
        try {
          const status = await getProductIngestionStatus(activeProductId);
          if (status.status === "ready") {
            setDocsReady(true);
            // Also update product list state
            setProducts((prev) =>
              prev.map((p) =>
                p.id === activeProductId ? { ...p, status: status.status, ingestion: status } : p
              )
            );
          } else {
            setProcessingWarning(true);
          }
        } catch {
          // Network error -- let the message through anyway
        }
      }
      sendMessage(text, images);
    },
    [sendMessage, docsReady, activeProductId]
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

  const chatDisabled = isStreaming || !activeProduct;

  if (!activeProduct) {
    if (productsLoadError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-50 px-6 dark:bg-neutral-950">
          <div className="max-w-lg rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            <p className="font-medium">Backend unreachable</p>
            <p className="mt-2">{productsLoadError}</p>
          </div>
          <button
            type="button"
            onClick={() => void loadProducts()}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Retry
          </button>
          <Link
            href="/"
            className="text-sm text-orange-600 hover:underline dark:text-orange-400"
          >
            Back to products
          </Link>
        </div>
      );
    }
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-neutral-950">
        <div className="inline-flex items-center gap-2 text-sm text-gray-500 dark:text-neutral-400">
          {productsLoading ? (
            <>
              <Loader2 suppressHydrationWarning className="h-4 w-4 animate-spin" />
              Loading product workspace...
            </>
          ) : (
            "No matching product. Go back and pick one from the list."
          )}
        </div>
      </div>
    );
  }

  const ingestionLabel =
    activeProduct.ingestion.status === "ready"
      ? "Ready"
      : activeProduct.ingestion.status === "processing"
        ? "Ingesting"
        : "Draft";

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

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="relative flex shrink-0 items-center border-b border-gray-200 bg-white px-3 py-3 dark:border-neutral-700 dark:bg-neutral-900 sm:px-5 sm:py-3.5">
          <div className="relative z-10 flex min-w-0 flex-1 items-center gap-1 sm:gap-2">
            <Link
              href="/"
              className="-m-1 inline-flex shrink-0 rounded-md p-1 text-gray-500 transition-colors hover:text-orange-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-500 dark:text-neutral-500 dark:hover:text-orange-400"
              title="Home"
              aria-label="Home"
            >
              <Home suppressHydrationWarning className="h-5 w-5" strokeWidth={2} aria-hidden />
            </Link>
            {!historyOpen && (
              <button
                type="button"
                onClick={() => setHistoryOpen(true)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-gray-200 bg-white text-gray-500 transition-colors hover:text-gray-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:text-neutral-100"
                title="Show history"
              >
                <PanelLeftOpen suppressHydrationWarning className="h-4 w-4" />
              </button>
            )}
          </div>

          <Link
            href="/"
            className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2 text-xl font-black uppercase tracking-[0.38em] text-orange-600 transition-colors hover:text-orange-700 sm:text-2xl sm:tracking-[0.42em] xl:left-[calc(50%-10rem)] dark:text-orange-400 dark:hover:text-orange-300"
            title="Back to workspaces"
          >
            Prox
          </Link>

          <div className="relative z-10 flex min-w-0 flex-1 items-center justify-end gap-2">
            <select
              value={activeProductId}
              onChange={(event) => {
                const nextProductId = event.target.value;
                window.location.href = `/products/${nextProductId}`;
              }}
              className="h-8 max-w-[9rem] rounded-lg border border-gray-200 bg-white px-2 text-xs text-gray-700 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 sm:max-w-[14rem]"
              aria-label="Switch product workspace"
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
              className="flex h-8 items-center gap-2 rounded-lg border border-gray-200 bg-white px-2.5 text-xs text-gray-600 transition-colors hover:text-gray-900 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:text-white xl:hidden"
              title="Workspace, sources, and artifacts"
            >
              <LibraryBig suppressHydrationWarning className="h-4 w-4" />
              Context
            </button>
            <ThemeToggle />
          </div>
        </header>

        {activeProduct.ingestion.status !== "ready" && (
          <div className="flex shrink-0 items-center justify-between border-b border-orange-200 bg-orange-50 px-5 py-2 text-xs text-orange-700 dark:border-orange-900/40 dark:bg-orange-950/30 dark:text-orange-200">
            <span>
              {activeProduct.ingestion.status === "processing"
                ? activeProduct.ingestion.message || "Documents are being processed."
                : activeProduct.ingestion.message || "Upload documents to get started."}
            </span>
            <button
              type="button"
              onClick={() => void refreshStatus()}
              disabled={refreshing}
              className="ml-3 inline-flex shrink-0 items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium text-orange-600 transition-colors hover:bg-orange-100 disabled:opacity-50 dark:text-orange-300 dark:hover:bg-orange-900/40"
              title="Refresh status"
            >
              <RefreshCw suppressHydrationWarning className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>
        )}

        <div className="grid min-h-0 flex-1 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="flex min-h-0 flex-col">
            <div className="min-h-0 flex-1 overflow-y-auto">
              {messages.length === 0 ? (
                <div className="flex min-h-full">
                  <WelcomeScreen
                    productName={activeProduct.name}
                    productDescription={
                      activeProduct.description || "Choose a product and ask grounded questions."
                    }
                    quickActions={activeProduct.quick_actions}
                    onQuickAction={(msg) => handleSend(msg)}
                  />
                </div>
              ) : (
                <div className="mx-auto max-w-6xl space-y-6 px-6 py-4">
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

            <div className="shrink-0 border-t border-gray-200 bg-white dark:border-neutral-700 dark:bg-neutral-900">
              {processingWarning && (
                <div className="mx-auto flex max-w-6xl items-center gap-2 border-b border-amber-200 bg-amber-50 px-6 py-2 text-xs text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200">
                  <AlertTriangle suppressHydrationWarning className="h-3.5 w-3.5 shrink-0" />
                  <span>Some documents are still processing. Answers may not cover those docs yet.</span>
                  <button
                    type="button"
                    onClick={() => setProcessingWarning(false)}
                    className="ml-auto text-[10px] font-medium text-amber-500 hover:text-amber-700 dark:text-amber-400 dark:hover:text-amber-200"
                  >
                    Dismiss
                  </button>
                </div>
              )}
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

          <aside className="hidden min-h-0 flex-col border-l border-gray-200 bg-white dark:border-neutral-700 dark:bg-neutral-900 xl:flex">
            <div className="shrink-0 border-b border-gray-200 px-4 py-3 dark:border-neutral-700">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-neutral-500">
                Product workspace
              </p>
              <div className="mt-1.5 flex items-center gap-2.5">
                {activeProduct.logo_url && (
                  <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-md border border-gray-200/90 bg-gray-50 dark:border-neutral-600 dark:bg-neutral-800/90">
                    {/* eslint-disable-next-line @next/next/no-img-element -- backend asset URL */}
                    <img
                      src={buildBackendUrl(activeProduct.logo_url)}
                      alt=""
                      className="h-full w-full object-contain p-0.5"
                    />
                  </div>
                )}
                <h2 className="text-sm font-semibold leading-snug text-gray-900 dark:text-neutral-100">
                  {activeProduct.name}
                </h2>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-gray-600 dark:text-neutral-400">
                {activeProduct.description || "Local-first multimodal manual assistant"}
              </p>
              <div className="mt-2.5 flex items-center text-[11px] text-gray-500 dark:text-neutral-500">
                <span>
                  {activeProduct.document_count}{" "}
                  {activeProduct.document_count === 1 ? "manual" : "manuals"}
                </span>
                <span className="mx-2 text-gray-300 dark:text-neutral-600" aria-hidden>
                  ·
                </span>
                <span className="font-medium text-gray-600 dark:text-neutral-400">{ingestionLabel}</span>
                <button
                  type="button"
                  onClick={() => void refreshStatus()}
                  disabled={refreshing}
                  className="ml-1.5 inline-flex items-center rounded p-0.5 text-gray-400 transition-colors hover:text-orange-500 disabled:opacity-50 dark:text-neutral-500 dark:hover:text-orange-400"
                  title="Refresh status"
                >
                  <RefreshCw suppressHydrationWarning className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
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
        productName={activeProduct.name}
        productDescription={
          activeProduct.description || "Local-first multimodal manual assistant"
        }
        documentCount={activeProduct.document_count}
        ingestionLabel={ingestionLabel}
        selectedSource={selectedSource}
        artifacts={artifacts}
      />
    </div>
  );
}
