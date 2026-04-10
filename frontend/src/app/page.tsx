"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { LibraryBig, Loader2, PanelLeftOpen, Plus } from "lucide-react";
import {
  createProduct,
  fetchProducts,
  getProductIngestionStatus,
  ProductSummary,
  startProductIngestion,
  uploadProductDocuments,
  uploadProductLogo,
} from "@/lib/api";
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
import { DialogShell } from "@/components/ui/dialog-shell";
import type { SelectedSourcePage } from "@/types/events";

const ACTIVE_PRODUCT_STORAGE_KEY = "prox_active_product_id";

export default function Home() {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [activeProductId, setActiveProductId] = useState("");
  const [conversationId, setConversationId] = useState<string>(() => crypto.randomUUID());
  const [selectedSource, setSelectedSource] = useState<SelectedSourcePage | null>(null);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [mobileContextOpen, setMobileContextOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createFiles, setCreateFiles] = useState<File[]>([]);
  const [createLogo, setCreateLogo] = useState<File | null>(null);
  const [isSubmittingProduct, setIsSubmittingProduct] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeProduct = useMemo(
    () => products.find((product) => product.id === activeProductId) ?? null,
    [products, activeProductId]
  );

  const { messages, isStreaming, session, sendMessage, stopStreaming, clearMessages } =
    useChat(activeProductId || "vulcan-omnipro-220", conversationId);

  const artifacts = useMemo(() => extractArtifactsFromMessages(messages), [messages]);

  const loadProducts = useCallback(async () => {
    const data = await fetchProducts();
    setProducts(data.products);
    setActiveProductId((current) => {
      if (current && data.products.some((product) => product.id === current)) return current;
      const stored = window.localStorage.getItem(ACTIVE_PRODUCT_STORAGE_KEY);
      if (stored && data.products.some((product) => product.id === stored)) return stored;
      return data.default_product_id;
    });
  }, []);

  useEffect(() => {
    void loadProducts();
  }, [loadProducts]);

  useEffect(() => {
    if (!activeProduct) return;
    window.localStorage.setItem(ACTIVE_PRODUCT_STORAGE_KEY, activeProduct.id);
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
        // Keep last known status if polling fails.
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

  const handleCreateProduct = useCallback(async () => {
    if (!createName.trim()) return;
    setIsSubmittingProduct(true);
    try {
      const created = await createProduct(createName.trim(), createDescription.trim());
      if (createLogo) {
        await uploadProductLogo(created.id, createLogo);
      }
      if (createFiles.length > 0) {
        await uploadProductDocuments(created.id, createFiles);
        await startProductIngestion(created.id);
      }
      await loadProducts();
      setActiveProductId(created.id);
      setCreateName("");
      setCreateDescription("");
      setCreateFiles([]);
      setCreateLogo(null);
      setCreateOpen(false);
    } finally {
      setIsSubmittingProduct(false);
    }
  }, [createDescription, createFiles, createLogo, createName, loadProducts]);

  const chatDisabled = isStreaming || !activeProduct || activeProduct.ingestion.status !== "ready";

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-neutral-950">
      {historyOpen && activeProduct && (
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
            <span className="text-lg">&#x1F525;</span>
            <div>
              <h1 className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
                {activeProduct?.name ?? "ProductManualQnA"}
              </h1>
              <p className="text-xs text-gray-400 dark:text-neutral-500">
                {activeProduct?.description || "Local-first multimodal manual assistant"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={activeProductId}
              onChange={(event) => setActiveProductId(event.target.value)}
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
              onClick={() => setCreateOpen(true)}
              className="inline-flex h-8 items-center gap-1 rounded-lg border border-gray-200 bg-white px-2.5 text-xs text-gray-700 transition-colors hover:border-orange-300 hover:text-orange-600 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-200 dark:hover:border-orange-500 dark:hover:text-orange-300"
            >
              <Plus suppressHydrationWarning className="h-3.5 w-3.5" />
              Add manual
            </button>
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

        {activeProduct && activeProduct.ingestion.status !== "ready" && (
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

        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="flex min-h-full">
              <WelcomeScreen
                productName={activeProduct?.name ?? "ProductManualQnA"}
                productDescription={
                  activeProduct?.description || "Choose a product and ask grounded questions."
                }
                quickActions={activeProduct?.quick_actions ?? []}
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

      <MobileContextPanel
        open={mobileContextOpen}
        onClose={() => setMobileContextOpen(false)}
        productId={activeProduct?.id ?? "vulcan-omnipro-220"}
        session={session}
        selectedSource={selectedSource}
        artifacts={artifacts}
      />

      <aside className="hidden w-72 shrink-0 border-l border-gray-200 bg-white dark:border-neutral-700 dark:bg-neutral-900 lg:flex lg:flex-col">
        <div className="flex-1 space-y-6 overflow-y-auto p-4">
          <SessionSidebar session={session} />
          {activeProduct && (
            <SourceViewer
              productId={activeProduct.id}
              selectedSource={selectedSource}
              artifacts={artifacts}
            />
          )}
        </div>
      </aside>

      {createOpen && (
        <DialogShell
          title="Create product"
          subtitle="Add a new product profile, upload manuals, and start local ingestion."
          onClose={() => !isSubmittingProduct && setCreateOpen(false)}
          sizeClassName="max-w-lg"
          contentClassName="p-5 space-y-4"
        >
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
              Product name
            </label>
            <input
              value={createName}
              onChange={(event) => setCreateName(event.target.value)}
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-orange-400 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
              placeholder="Bench drill manual"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
              Description
            </label>
            <textarea
              value={createDescription}
              onChange={(event) => setCreateDescription(event.target.value)}
              rows={3}
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-orange-400 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
              placeholder="What is this product and how should the assistant present it?"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
              Logo image (optional)
            </label>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setCreateLogo(event.target.files?.[0] ?? null)}
              className="block w-full text-xs text-gray-600 dark:text-neutral-300"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
              Documents
            </label>
            <input
              type="file"
              multiple
              accept=".pdf"
              onChange={(event) => setCreateFiles(Array.from(event.target.files ?? []))}
              className="block w-full text-xs text-gray-600 dark:text-neutral-300"
            />
            <p className="text-xs text-gray-400 dark:text-neutral-500">
              PDFs are rendered locally into page images and chunk indexes during background ingestion.
            </p>
          </div>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setCreateOpen(false)}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 dark:border-neutral-700 dark:text-neutral-300"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleCreateProduct()}
              disabled={isSubmittingProduct || !createName.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isSubmittingProduct && (
                <Loader2 suppressHydrationWarning className="h-4 w-4 animate-spin" />
              )}
              Create
            </button>
          </div>
        </DialogShell>
      )}
    </div>
  );
}
