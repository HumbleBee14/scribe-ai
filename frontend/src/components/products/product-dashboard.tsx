"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  ChevronRight,
  FileText,
  Loader2,
  Pencil,
  Plus,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";
import { BACKEND_URL, fetchProducts, ProductSummary } from "@/lib/api";
import { CreateProductDialog } from "@/components/products/create-product-dialog";

/** Stable default so `useEffect` deps are not a new `[]` every render (that caused infinite /api/products). */
const EMPTY_PRODUCTS: ProductSummary[] = [];

/** Compact workspace cards: narrow width and tight vertical rhythm. */
const WORKSPACE_CARD_CLASS = "w-full max-w-[17.5rem] sm:max-w-[18.25rem]";

interface Props {
  initialProducts?: ProductSummary[];
  initialDefaultProductId?: string;
}

export function ProductDashboard({
  initialProducts = EMPTY_PRODUCTS,
  initialDefaultProductId = "",
}: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [editProduct, setEditProduct] = useState<ProductSummary | null>(null);
  const [items, setItems] = useState(initialProducts);
  const [defaultProductId, setDefaultProductId] = useState(initialDefaultProductId);
  const [isLoading, setIsLoading] = useState(initialProducts.length === 0);
  const [loadError, setLoadError] = useState<string | null>(null);

  const formatLoadError = useCallback((e: unknown) => {
    if (e instanceof TypeError && e.message === "Failed to fetch") {
      return `Could not reach the API at ${BACKEND_URL}. Start the backend (e.g. uvicorn) or set NEXT_PUBLIC_BACKEND_URL if it runs elsewhere.`;
    }
    if (e instanceof Error) return e.message;
    return "Could not load products.";
  }, []);

  const reloadProducts = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const data = await fetchProducts();
      setItems(data.products);
      setDefaultProductId(data.default_product_id);
    } catch (e) {
      setLoadError(formatLoadError(e));
    } finally {
      setIsLoading(false);
    }
  }, [formatLoadError]);

  useEffect(() => {
    if (initialProducts.length > 0) return;
    void reloadProducts();
  }, [initialProducts.length, reloadProducts]);

  const sortedProducts = useMemo(
    () =>
      [...items].sort((a, b) => {
        if (a.id === defaultProductId) return -1;
        if (b.id === defaultProductId) return 1;
        return a.name.localeCompare(b.name);
      }),
    [defaultProductId, items]
  );

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-gradient-to-b from-stone-100 via-gray-50 to-orange-50/40 dark:from-neutral-950 dark:via-neutral-950 dark:to-orange-950/25">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[min(520px,55vh)] bg-[radial-gradient(ellipse_80%_60%_at_50%_-10%,rgba(249,115,22,0.22),transparent)] dark:bg-[radial-gradient(ellipse_80%_60%_at_50%_-10%,rgba(249,115,22,0.12),transparent)]"
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-orange-200/80 to-transparent dark:via-orange-500/30" aria-hidden />

      <div className="relative mx-auto max-w-5xl px-4 pb-20 pt-14 sm:px-6 lg:px-8">
        <header className="text-center">
          <div className="relative mx-auto flex min-h-[7.5rem] w-full max-w-4xl flex-col items-center justify-center py-4 sm:min-h-[8.5rem] sm:py-6">
            <span
              className="pointer-events-none absolute left-1/2 top-[52%] z-0 -translate-x-1/2 -translate-y-1/2 select-none whitespace-nowrap bg-gradient-to-br from-orange-400/25 via-orange-500/20 to-orange-600/15 bg-clip-text text-[clamp(3.75rem,18vw,10.5rem)] font-black uppercase leading-[0.85] tracking-[0.02em] text-transparent dark:from-orange-400/20 dark:via-orange-500/15 dark:to-orange-600/10 sm:tracking-[0.04em]"
              aria-hidden
            >
              PROX
            </span>
            <h1 className="relative z-10 mx-auto max-w-2xl text-balance text-3xl font-bold tracking-tight text-gray-900 drop-shadow-[0_1px_0_rgba(255,255,255,0.9)] sm:text-4xl lg:text-[2.35rem] lg:leading-tight dark:text-white dark:drop-shadow-[0_1px_0_rgba(0,0,0,0.5)]">
              Ask your manual. I&apos;m your live guide.
            </h1>
          </div>

          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-orange-500 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-orange-500/25 transition hover:bg-orange-600 hover:shadow-orange-500/35 dark:shadow-orange-900/40 sm:mt-6"
          >
            <Plus suppressHydrationWarning className="h-4 w-4" />
            Add product
          </button>
        </header>

        <ul className="mx-auto mt-8 grid max-w-3xl gap-4 sm:grid-cols-3 sm:gap-5">
          <li className="rounded-2xl border border-white/80 bg-white/70 px-4 py-4 text-center shadow-sm backdrop-blur-sm dark:border-neutral-800 dark:bg-neutral-900/70">
            <ScanSearch className="mx-auto h-5 w-5 text-orange-500 dark:text-orange-400" aria-hidden />
            <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-neutral-100">Search and retrieve</p>
            <p className="mt-1 text-xs leading-relaxed text-gray-500 dark:text-neutral-400">
              Hybrid search across manual text with page-level references.
            </p>
          </li>
          <li className="rounded-2xl border border-white/80 bg-white/70 px-4 py-4 text-center shadow-sm backdrop-blur-sm dark:border-neutral-800 dark:bg-neutral-900/70">
            <BookOpen className="mx-auto h-5 w-5 text-orange-500 dark:text-orange-400" aria-hidden />
            <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-neutral-100">Exact + visual</p>
            <p className="mt-1 text-xs leading-relaxed text-gray-500 dark:text-neutral-400">
              Specs, tables, and page images when the answer needs proof.
            </p>
          </li>
          <li className="rounded-2xl border border-white/80 bg-white/70 px-4 py-4 text-center shadow-sm backdrop-blur-sm dark:border-neutral-800 dark:bg-neutral-900/70 sm:col-span-1">
            <ShieldCheck className="mx-auto h-5 w-5 text-orange-500 dark:text-orange-400" aria-hidden />
            <p className="mt-2 text-sm font-semibold text-gray-900 dark:text-neutral-100">Isolated workspaces</p>
            <p className="mt-1 text-xs leading-relaxed text-gray-500 dark:text-neutral-400">
              Each product keeps its own files, index, and chat history.
            </p>
          </li>
        </ul>

        <section className="mt-10" aria-labelledby="workspaces-heading">
          <div className="mb-8 text-center">
            <h2
              id="workspaces-heading"
              className="text-sm font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-neutral-500"
            >
              Your workspaces
            </h2>
            <p className="mt-2 text-sm text-gray-500 dark:text-neutral-500">
              Select a product to open its assistant, or add a new profile.
            </p>
          </div>

          <div className="mx-auto flex w-full max-w-6xl flex-col items-stretch gap-4 sm:flex-row sm:flex-wrap sm:items-stretch sm:justify-center">
            {loadError && (
              <div className="w-full rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
                <p className="font-medium">Backend unreachable</p>
                <p className="mt-2 text-red-700/90 dark:text-red-300/90">{loadError}</p>
                <button
                  type="button"
                  onClick={() => void reloadProducts()}
                  className="mt-3 rounded-lg bg-red-600 px-3 py-2 text-xs font-medium text-white hover:bg-red-700"
                >
                  Retry
                </button>
              </div>
            )}
            {isLoading && (
              <div
                className={`inline-flex ${WORKSPACE_CARD_CLASS} items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-8 text-sm text-gray-500 shadow-sm dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400 sm:w-auto`}
              >
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading products...
              </div>
            )}
            {!isLoading && !loadError && sortedProducts.length === 0 && (
              <div
                className={`${WORKSPACE_CARD_CLASS} rounded-2xl border border-dashed border-gray-300 bg-white/60 px-6 py-12 text-center dark:border-neutral-700 dark:bg-neutral-900/40`}
              >
                <p className="text-sm font-medium text-gray-700 dark:text-neutral-300">No workspaces yet</p>
                <p className="mt-2 text-sm text-gray-500 dark:text-neutral-500">
                  Create a product and attach PDF manuals to get started.
                </p>
              </div>
            )}
            {sortedProducts.map((product) => (
              <div
                key={product.id}
                className={`flex shrink-0 self-stretch ${WORKSPACE_CARD_CLASS}`}
              >
                <Link
                  href={`/products/${product.id}`}
                  className="group flex h-full w-full flex-col rounded-xl border border-gray-200 bg-white p-3.5 shadow-sm transition-colors hover:border-orange-300 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:border-orange-500"
                >
                  <div className="flex shrink-0 items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <h2 className="line-clamp-2 text-base font-semibold leading-tight text-gray-900 dark:text-neutral-100">
                        {product.name}
                      </h2>
                      <p className="mt-1 min-h-[2.35rem] line-clamp-2 text-xs leading-snug text-gray-500 dark:text-neutral-400">
                        {product.description || "Manual assistant workspace"}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-0.5">
                      <button
                        type="button"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setEditProduct(product); }}
                        className="flex h-6 w-6 items-center justify-center rounded-md text-gray-300 opacity-0 transition-all hover:bg-gray-100 hover:text-gray-600 group-hover:opacity-100 dark:text-neutral-600 dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
                        title="Edit product"
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                      <ChevronRight className="h-4 w-4 text-gray-300 transition-colors group-hover:text-orange-500 dark:text-neutral-600 dark:group-hover:text-orange-400" />
                    </div>
                  </div>

                  <div className="mt-2.5 flex min-h-[1.25rem] shrink-0 flex-wrap gap-1.5 text-[11px] leading-tight content-start">
                    {product.categories?.length > 0 ? (
                      product.categories.slice(0, 3).map((cat) => (
                        <span
                          key={cat}
                          className="rounded-full bg-gray-100 px-2 py-0.5 text-gray-600 dark:bg-neutral-800 dark:text-neutral-300"
                        >
                          {cat}
                        </span>
                      ))
                    ) : null}
                  </div>

                  <div className="mt-auto flex shrink-0 items-center justify-between pt-2.5 text-[11px]">
                    <span className="inline-flex items-center gap-1 text-gray-400 dark:text-neutral-500">
                      <FileText className="h-3 w-3 shrink-0" />
                      {product.document_count} {product.document_count === 1 ? "manual" : "manuals"}
                    </span>
                    <span
                      className={`inline-flex items-center gap-1.5 font-medium ${
                        product.ingestion.status === "ready"
                          ? "text-green-600 dark:text-green-400"
                          : product.ingestion.status === "processing"
                            ? "text-orange-500 dark:text-orange-300"
                            : "text-gray-400 dark:text-neutral-500"
                      }`}
                    >
                      {product.ingestion.status === "processing" && (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      )}
                      {product.ingestion.status === "ready" ? "\u2022 Ready" : product.ingestion.status === "processing" ? "Ingesting..." : "\u2022 Draft"}
                    </span>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        </section>
      </div>

      {(createOpen || editProduct) && (
        <CreateProductDialog
          key={editProduct?.id ?? "create"}
          open
          editMode={!!editProduct}
          initialData={editProduct ?? undefined}
          onClose={() => { setCreateOpen(false); setEditProduct(null); }}
          onCreated={(product) => {
            if (editProduct) {
              setItems((prev) => prev.map((p) => p.id === product.id ? product : p));
            } else {
              setItems((prev) => [...prev, product]);
            }
            setCreateOpen(false);
            setEditProduct(null);
          }}
          onDeleted={(deletedId) => {
            setItems((prev) => prev.filter((p) => p.id !== deletedId));
            setEditProduct(null);
          }}
        />
      )}
    </div>
  );
}
