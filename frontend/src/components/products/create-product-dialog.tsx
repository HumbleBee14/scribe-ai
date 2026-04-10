"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import {
  createProduct,
  ProductSummary,
  startProductIngestion,
  uploadProductDocuments,
  uploadProductLogo,
} from "@/lib/api";
import { DialogShell } from "@/components/ui/dialog-shell";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (product: ProductSummary) => void;
}

export function CreateProductDialog({ open, onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [logo, setLogo] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!open) return null;

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      let product = await createProduct(name.trim(), description.trim());
      if (logo) {
        product = await uploadProductLogo(product.id, logo);
      }
      if (files.length > 0) {
        product = await uploadProductDocuments(product.id, files);
        await startProductIngestion(product.id);
        product = { ...product, ingestion: { ...product.ingestion, status: "processing" } };
      }
      setName("");
      setDescription("");
      setFiles([]);
      setLogo(null);
      onCreated(product);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DialogShell
      title="Create product"
      subtitle="Add a product profile, optional logo, and up to 10 manuals."
      onClose={() => !isSubmitting && onClose()}
      sizeClassName="max-w-lg"
      contentClassName="p-5 space-y-4"
    >
      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
          Product name
        </label>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-orange-400 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-100"
          placeholder="Bench drill manual"
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
          Description
        </label>
        <textarea
          value={description}
          onChange={(event) => setDescription(event.target.value)}
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
          onChange={(event) => setLogo(event.target.files?.[0] ?? null)}
          className="block w-full text-xs text-gray-600 dark:text-neutral-300"
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs font-medium text-gray-500 dark:text-neutral-400">
          Manuals
        </label>
        <input
          type="file"
          multiple
          accept=".pdf"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          className="block w-full text-xs text-gray-600 dark:text-neutral-300"
        />
        <p className="text-xs text-gray-400 dark:text-neutral-500">
          Original files are stored with the product and ingested into page images and chunks.
        </p>
      </div>

      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 dark:border-neutral-700 dark:text-neutral-300"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={isSubmitting || !name.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {isSubmitting && (
            <Loader2 suppressHydrationWarning className="h-4 w-4 animate-spin" />
          )}
          Create
        </button>
      </div>
    </DialogShell>
  );
}
