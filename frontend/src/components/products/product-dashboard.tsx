"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronRight, FileText, Loader2, Pencil, Plus } from "lucide-react";
import { BACKEND_URL, fetchProducts, ProductSummary } from "@/lib/api";
import { CreateProductDialog } from "@/components/products/create-product-dialog";

/** Stable default so `useEffect` deps are not a new `[]` every render (that caused infinite /api/products). */
const EMPTY_PRODUCTS: ProductSummary[] = [];

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
    <div className="min-h-screen bg-gray-50 px-6 py-10 dark:bg-neutral-950">
      <div className="mx-auto max-w-6xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-orange-500 dark:text-orange-400">
              ProductManualQnA
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-gray-900 dark:text-neutral-100">
              Your Product Workspaces
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-gray-500 dark:text-neutral-400">
              Upload any product manual and get an AI assistant that answers questions with
              exact data, diagrams, and page references. Each workspace keeps its own documents,
              knowledge base, and conversations.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-orange-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-orange-600"
          >
            <Plus suppressHydrationWarning className="h-4 w-4" />
            Add product
          </button>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {loadError && (
            <div className="md:col-span-2 xl:col-span-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
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
            <div className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading products...
            </div>
          )}
          {!isLoading && !loadError && sortedProducts.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-neutral-400">
              No products yet. Use Add product to create one.
            </p>
          )}
          {sortedProducts.map((product) => (
            <Link
              key={product.id}
              href={`/products/${product.id}`}
              className="group rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition-colors hover:border-orange-300 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:border-orange-500"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-neutral-100">
                    {product.name}
                  </h2>
                  <p className="mt-2 text-sm text-gray-500 dark:text-neutral-400">
                    {product.description || "Manual assistant workspace"}
                  </p>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); setEditProduct(product); }}
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-gray-300 opacity-0 transition-all hover:bg-gray-100 hover:text-gray-600 group-hover:opacity-100 dark:text-neutral-600 dark:hover:bg-neutral-800 dark:hover:text-neutral-300"
                    title="Edit product"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <ChevronRight className="h-5 w-5 text-gray-300 transition-colors group-hover:text-orange-500 dark:text-neutral-600 dark:group-hover:text-orange-400" />
                </div>
              </div>

              {(product.categories?.length ? product.categories : [product.domain]).length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2 text-xs">
                  {(product.categories?.length ? product.categories : [product.domain]).slice(0, 3).map((cat) => (
                    <span
                      key={cat}
                      className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-600 dark:bg-neutral-800 dark:text-neutral-300"
                    >
                      {cat}
                    </span>
                  ))}
                </div>
              )}

              <div className="mt-4 flex items-center justify-between text-xs">
                <span className="inline-flex items-center gap-1 text-gray-400 dark:text-neutral-500">
                  <FileText className="h-3.5 w-3.5" />
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
          ))}
        </div>
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
