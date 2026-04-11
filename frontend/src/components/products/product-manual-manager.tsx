"use client";

import { useRef, useState } from "react";
import { Loader2, RefreshCcw, Trash2, Upload } from "lucide-react";
import {
  deleteProductDocument,
  ProductSummary,
  replaceProductDocument,
  startProductIngestion,
  uploadProductDocuments,
} from "@/lib/api";

interface Props {
  product: ProductSummary;
  onProductChange: (product: ProductSummary) => void;
}

export function ProductManualManager({ product, onProductChange }: Props) {
  const uploadRef = useRef<HTMLInputElement>(null);
  const replaceRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [isBusy, setIsBusy] = useState<string | null>(null);

  const canUpload = product.document_count < product.max_documents;

  const triggerIngest = async (nextProduct: ProductSummary) => {
    await startProductIngestion(nextProduct.id);
    onProductChange({
      ...nextProduct,
      ingestion: {
        ...nextProduct.ingestion,
        status: "processing",
        stage: "queued",
        progress: 0.05,
        message: `Ingestion queued for ${nextProduct.name}.`,
      },
    });
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0 || !canUpload) return;
    setIsBusy("upload");
    try {
      const nextProduct = await uploadProductDocuments(product.id, Array.from(files));
      await triggerIngest(nextProduct);
    } finally {
      setIsBusy(null);
      if (uploadRef.current) uploadRef.current.value = "";
    }
  };

  const handleReplace = async (sourceId: string, file: File | null) => {
    if (!file) return;
    setIsBusy(`replace:${sourceId}`);
    try {
      const nextProduct = await replaceProductDocument(product.id, sourceId, file);
      await triggerIngest(nextProduct);
    } finally {
      setIsBusy(null);
      const input = replaceRefs.current[sourceId];
      if (input) input.value = "";
    }
  };

  const handleDelete = async (sourceId: string) => {
    setIsBusy(`delete:${sourceId}`);
    try {
      const nextProduct = await deleteProductDocument(product.id, sourceId);
      if (nextProduct.document_count > 0) {
        await triggerIngest(nextProduct);
      } else {
        onProductChange(nextProduct);
      }
    } finally {
      setIsBusy(null);
    }
  };

  return (
    <div className="space-y-4 rounded-2xl border border-gray-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
            Product manuals
          </h3>
          <p className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
            {product.document_count}/{product.max_documents} manuals attached. Original files stay
            stored under this product profile.
          </p>
        </div>
        <div>
          <input
            ref={uploadRef}
            type="file"
            accept=".pdf"
            multiple
            className="hidden"
            onChange={(event) => void handleUpload(event.target.files)}
          />
          <button
            type="button"
            disabled={!canUpload || isBusy !== null}
            onClick={() => uploadRef.current?.click()}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-xs font-medium text-gray-700 disabled:opacity-50 dark:border-neutral-700 dark:text-neutral-200"
          >
            {isBusy === "upload" ? (
              <Loader2 suppressHydrationWarning className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Upload suppressHydrationWarning className="h-3.5 w-3.5" />
            )}
            Add manual
          </button>
        </div>
      </div>

      {!canUpload && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-700 dark:border-orange-900/40 dark:bg-orange-950/30 dark:text-orange-200">
          This product already has the maximum of {product.max_documents} manuals.
        </div>
      )}

      <div className="space-y-3">
        {product.sources.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-200 px-3 py-4 text-sm text-gray-400 dark:border-neutral-700 dark:text-neutral-500">
            No manuals attached yet.
          </div>
        ) : (
          product.sources.map((source) => (
            <div
              key={source.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 px-3 py-3 dark:border-neutral-700"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-gray-900 dark:text-neutral-100">
                  {source.label}
                </div>
                <div className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
                  {source.type.replace("_", " ")}
                  {source.pages ? ` · ${source.pages} pages` : ""}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  ref={(node) => {
                    replaceRefs.current[source.id] = node;
                  }}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={(event) =>
                    void handleReplace(source.id, event.target.files?.[0] ?? null)
                  }
                />
                <button
                  type="button"
                  disabled={isBusy !== null}
                  onClick={() => replaceRefs.current[source.id]?.click()}
                  className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1.5 text-xs text-gray-600 disabled:opacity-50 dark:border-neutral-700 dark:text-neutral-300"
                >
                  {isBusy === `replace:${source.id}` ? (
                    <Loader2 suppressHydrationWarning className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RefreshCcw suppressHydrationWarning className="h-3.5 w-3.5" />
                  )}
                  Replace
                </button>
                <button
                  type="button"
                  disabled={isBusy !== null}
                  onClick={() => void handleDelete(source.id)}
                  className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-2.5 py-1.5 text-xs text-red-600 disabled:opacity-50 dark:border-red-900/40 dark:text-red-300"
                >
                  {isBusy === `delete:${source.id}` ? (
                    <Loader2 suppressHydrationWarning className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 suppressHydrationWarning className="h-3.5 w-3.5" />
                  )}
                  Delete
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
