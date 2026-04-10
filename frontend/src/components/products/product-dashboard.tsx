"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ChevronRight, FileText, Loader2, Plus } from "lucide-react";
import { fetchProducts, ProductSummary } from "@/lib/api";
import { CreateProductDialog } from "@/components/products/create-product-dialog";

interface Props {
  initialProducts?: ProductSummary[];
  initialDefaultProductId?: string;
}

export function ProductDashboard({
  initialProducts = [],
  initialDefaultProductId = "",
}: Props) {
  const [createOpen, setCreateOpen] = useState(false);
  const [items, setItems] = useState(initialProducts);
  const [defaultProductId, setDefaultProductId] = useState(initialDefaultProductId);
  const [isLoading, setIsLoading] = useState(initialProducts.length === 0);

  useEffect(() => {
    if (initialProducts.length > 0) return;
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      try {
        const data = await fetchProducts();
        if (cancelled) return;
        setItems(data.products);
        setDefaultProductId(data.default_product_id);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [initialProducts]);

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
              Choose a product workspace
            </h1>
            <p className="mt-3 max-w-2xl text-sm text-gray-500 dark:text-neutral-400">
              Pick an existing product profile or create a new one. Each product keeps its
              own manuals, ingestion state, conversations, sources, and artifacts.
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
          {isLoading && (
            <div className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-500 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading products...
            </div>
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
                <ChevronRight className="h-5 w-5 text-gray-300 transition-colors group-hover:text-orange-500 dark:text-neutral-600 dark:group-hover:text-orange-400" />
              </div>

              <div className="mt-5 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-700 dark:bg-neutral-800 dark:text-neutral-200">
                  {product.document_count}/{product.max_documents} manuals
                </span>
                <span className="rounded-full bg-gray-100 px-2.5 py-1 text-gray-700 dark:bg-neutral-800 dark:text-neutral-200">
                  {product.domain}
                </span>
                <span
                  className={`rounded-full px-2.5 py-1 ${
                    product.ingestion.status === "ready"
                      ? "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-200"
                      : product.ingestion.status === "processing"
                        ? "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-200"
                        : "bg-gray-100 text-gray-700 dark:bg-neutral-800 dark:text-neutral-200"
                  }`}
                >
                  {product.ingestion.status}
                </span>
              </div>

              <div className="mt-5 flex items-center justify-between text-xs text-gray-400 dark:text-neutral-500">
                <span className="inline-flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5" />
                  {product.sources.length} attached docs
                </span>
                {product.ingestion.status === "processing" && (
                  <span className="inline-flex items-center gap-1 text-orange-500 dark:text-orange-300">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Ingesting
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      </div>

      <CreateProductDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(product) => {
          setItems((prev) => [...prev, product]);
          setCreateOpen(false);
        }}
      />
    </div>
  );
}
