"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { buildBackendUrl, type ProductSourceSummary } from "@/lib/api";
import { DialogShell } from "@/components/ui/dialog-shell";

interface Props {
  open: boolean;
  onClose: () => void;
  productId: string;
  sources: ProductSourceSummary[];
}

export function ManualPreviewDialog({ open, onClose, productId, sources }: Props) {
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  if (!open || sources.length === 0) return null;

  const activeSource = sources[activeTab];
  const pdfUrl = buildBackendUrl(
    `/api/products/${productId}/sources/${activeSource.id}/pdf`
  );

  return (
    <DialogShell
      title="Manual Preview"
      subtitle={activeSource?.label || "Document"}
      onClose={onClose}
      sizeClassName="max-w-5xl"
      panelClassName="h-[92vh]"
      contentClassName="flex flex-col min-h-0"
    >
      {/* Tabs */}
      {sources.length > 1 && (
        <div className="flex gap-1 border-b border-gray-200 dark:border-neutral-700 px-4 pt-2 shrink-0 overflow-x-auto">
          {sources.map((s, i) => (
            <button
              key={s.id}
              onClick={() => {
                setActiveTab(i);
                setLoading(true);
                setError(false);
              }}
              className={`whitespace-nowrap rounded-t-lg px-3 py-2 text-xs font-medium transition-colors ${
                i === activeTab
                  ? "bg-white dark:bg-neutral-800 text-orange-600 dark:text-orange-400 border border-b-0 border-gray-200 dark:border-neutral-700"
                  : "text-gray-500 dark:text-neutral-400 hover:text-gray-700 dark:hover:text-neutral-300"
              }`}
            >
              {s.label || s.id}
              {s.pages ? ` (${s.pages}p)` : ""}
            </button>
          ))}
        </div>
      )}

      {/* PDF viewer */}
      <div className="flex-1 min-h-0 relative">
        {loading && !error && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50 dark:bg-neutral-950 z-10">
            <Loader2 className="h-6 w-6 animate-spin text-orange-400" />
          </div>
        )}

        {error ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <p className="text-sm text-red-500 dark:text-red-400">Failed to load PDF</p>
              <button
                type="button"
                onClick={() => { setError(false); setLoading(true); }}
                className="mt-2 text-xs text-orange-500 hover:underline"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          <iframe
            key={activeSource.id}
            src={pdfUrl}
            className="h-full w-full border-0"
            title={activeSource.label || "PDF Preview"}
            onLoad={() => setLoading(false)}
            onError={() => { setLoading(false); setError(true); }}
          />
        )}
      </div>
    </DialogShell>
  );
}
