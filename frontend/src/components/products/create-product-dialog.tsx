"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle,
  FileText,
  FileUp,
  ImagePlus,
  Loader2,
  Trash2,
  X,
} from "lucide-react";
import {
  createProduct,
  deleteProduct,
  deleteProductDocument,
  fetchProduct,
  getProductIngestionStatus,
  ProductSummary,
  updateProduct,
  uploadProductDocuments,
  uploadProductLogo,
} from "@/lib/api";
import { DialogShell } from "@/components/ui/dialog-shell";

interface Props {
  open: boolean;
  editMode?: boolean;
  initialData?: ProductSummary;
  onClose: () => void;
  onCreated: (product: ProductSummary) => void;
  onDeleted?: (productId: string) => void;
}

const MAX_FILES = 10;

type UploadStatus = "uploading" | "done" | "failed";

export function CreateProductDialog({ open, editMode, initialData, onClose, onCreated, onDeleted }: Props) {
  // Form fields
  const [name, setName] = useState(initialData?.name ?? "");
  const [description, setDescription] = useState(initialData?.description ?? "");
  const [categoryInput, setCategoryInput] = useState("");
  const [categories, setCategories] = useState<string[]>(initialData?.categories ?? []);
  const [logo, setLogo] = useState<File | null>(null);

  // Create mode: local file queue (uploaded on submit)
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);

  // Edit mode: backend sources + live upload status
  const [existingSources, setExistingSources] = useState(initialData?.sources ?? []);
  const [fileStatuses, setFileStatuses] = useState<Map<string, UploadStatus>>(new Map());
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Shared state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitProgress, setSubmitProgress] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [processingStatus, setProcessingStatus] = useState(initialData?.ingestion?.status ?? "idle");
  const [processingMessage, setProcessingMessage] = useState(initialData?.ingestion?.message ?? "");

  const fileRef = useRef<HTMLInputElement>(null);
  const logoRef = useRef<HTMLInputElement>(null);

  const productId = editMode ? initialData?.id : undefined;
  const uploadingCount = [...fileStatuses.values()].filter((s) => s === "uploading").length;
  const isUploading = uploadingCount > 0;

  // Poll ingestion status while processing
  useEffect(() => {
    const pid = productId;
    if (processingStatus !== "processing" || !pid) return;
    const interval = setInterval(async () => {
      try {
        const status = await getProductIngestionStatus(pid);
        setProcessingStatus(status.status);
        setProcessingMessage(status.message || "");
        if (status.status !== "processing") clearInterval(interval);
      } catch { /* keep polling */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [processingStatus, productId]);

  if (!open) return null;

  const totalExisting = existingSources.length;
  const totalDocs = editMode ? totalExisting + uploadingCount : pendingFiles.length;
  const isProcessing = processingStatus === "processing";
  const isReady = processingStatus === "ready";

  // ---- Category helpers ----

  const addCategory = () => {
    const trimmed = categoryInput.trim().toLowerCase();
    if (trimmed && categories.length < 3 && !categories.includes(trimmed)) {
      setCategories([...categories, trimmed]);
      setCategoryInput("");
    }
  };

  // ---- File handling ----

  const handleFilesPicked = async (fileList: FileList | null) => {
    if (!fileList) return;
    const incoming = Array.from(fileList).filter((f) => f.name.endsWith(".pdf"));

    if (editMode && productId) {
      // Edit mode: upload immediately to backend
      for (const file of incoming) {
        if (totalExisting + uploadingCount >= MAX_FILES) break;
        setFileStatuses((prev) => new Map(prev).set(file.name, "uploading"));
        try {
          const updated = await uploadProductDocuments(productId, [file]);
          setExistingSources(updated.sources);
          setFileStatuses((prev) => new Map(prev).set(file.name, "done"));
        } catch {
          setFileStatuses((prev) => new Map(prev).set(file.name, "failed"));
        }
      }
    } else {
      // Create mode: queue locally
      setPendingFiles((prev) => {
        const existing = new Set(prev.map((f) => f.name));
        const unique = incoming.filter((f) => !existing.has(f.name));
        return [...prev, ...unique].slice(0, MAX_FILES);
      });
    }
  };

  const removePendingFile = (fileName: string) => {
    setPendingFiles((prev) => prev.filter((f) => f.name !== fileName));
  };

  const handleDeleteExisting = async (sourceId: string) => {
    if (!productId) return;
    setDeletingId(sourceId);
    try {
      const updated = await deleteProductDocument(productId, sourceId);
      setExistingSources(updated.sources);
    } catch { /* keep current state */ }
    setDeletingId(null);
  };

  // ---- Processing ----

  const handleProcess = async () => {
    const pid = productId;
    if (!pid) return;
    try {
      await startProductIngestion(pid);
      setProcessingStatus("processing");
      setProcessingMessage("Processing documents...");
    } catch { /* show current state */ }
  };

  // ---- Submit ----

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setIsSubmitting(true);
    try {
      if (editMode && productId) {
        // Edit: save metadata changes + logo
        setSubmitProgress("Saving changes...");
        await updateProduct(productId, {
          description: description.trim(),
          categories,
        });
        if (logo) {
          setSubmitProgress("Uploading logo...");
          await uploadProductLogo(productId, logo);
        }
        const product = await fetchProduct(productId);
        onCreated(product);
      } else {
        // Create: create product, then upload all pending files
        setSubmitProgress("Creating product...");
        const product = await createProduct(name.trim(), description.trim(), categories);

        if (logo) {
          setSubmitProgress("Uploading logo...");
          await uploadProductLogo(product.id, logo);
        }

        if (pendingFiles.length > 0) {
          for (let i = 0; i < pendingFiles.length; i++) {
            setSubmitProgress(`Uploading file ${i + 1}/${pendingFiles.length}...`);
            await uploadProductDocuments(product.id, [pendingFiles[i]]);
          }
        }

        setSubmitProgress("");
        const final = await fetchProduct(product.id);
        onCreated(final);
      }
    } finally {
      setIsSubmitting(false);
      setSubmitProgress("");
    }
  };

  // ---- Render ----

  return (
    <DialogShell
      title={editMode ? "Edit product" : "Create product workspace"}
      subtitle={editMode ? "Update product details and manage manuals." : "Set up a new product profile with manuals for AI-powered Q&A."}
      onClose={() => !isSubmitting && !isUploading && onClose()}
      sizeClassName="max-w-lg"
      contentClassName="p-5 space-y-5"
    >
      {/* Product name */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700 dark:text-neutral-300">
          Product name
        </label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={editMode}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100 disabled:opacity-70 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:focus:ring-orange-900"
          placeholder="e.g. DeWalt DWE7491RS Table Saw"
        />
      </div>

      {/* Description */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700 dark:text-neutral-300">
          Description
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
          className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none focus:border-orange-400 focus:ring-2 focus:ring-orange-100 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 dark:focus:ring-orange-900"
          placeholder="Brief product description for the AI assistant context"
        />
      </div>

      {/* Categories */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700 dark:text-neutral-300">
          Categories <span className="font-normal text-gray-400 dark:text-neutral-500">(up to 3)</span>
        </label>
        <div className="flex gap-2">
          <input
            value={categoryInput}
            onChange={(e) => setCategoryInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addCategory(); } }}
            disabled={categories.length >= 3}
            className="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-orange-400 dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-100 disabled:opacity-50"
            placeholder={categories.length >= 3 ? "Max 3 categories" : "e.g. power tools, woodworking"}
          />
          <button type="button" onClick={addCategory} disabled={!categoryInput.trim() || categories.length >= 3} className="rounded-lg bg-gray-100 px-3 py-2 text-xs font-medium text-gray-600 hover:bg-gray-200 disabled:opacity-40 dark:bg-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-600">
            Add
          </button>
        </div>
        {categories.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {categories.map((cat) => (
              <span key={cat} className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2.5 py-1 text-xs text-orange-700 dark:bg-orange-950/50 dark:text-orange-300">
                {cat}
                <button type="button" onClick={() => setCategories(categories.filter((c) => c !== cat))} className="hover:text-orange-900 dark:hover:text-orange-100">
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Logo */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700 dark:text-neutral-300">
          Logo <span className="font-normal text-gray-400 dark:text-neutral-500">(optional)</span>
        </label>
        <input ref={logoRef} type="file" accept="image/*" onChange={(e) => setLogo(e.target.files?.[0] ?? null)} className="hidden" />
        <button type="button" onClick={() => logoRef.current?.click()} className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs text-gray-600 hover:border-orange-300 transition-colors dark:border-neutral-600 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:border-orange-500">
          <ImagePlus className="h-3.5 w-3.5" />
          {logo ? logo.name.slice(0, 30) : "Choose image"}
        </button>
      </div>

      {/* Documents */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="block text-xs font-semibold text-gray-700 dark:text-neutral-300">
            Manuals <span className="font-normal text-gray-400 dark:text-neutral-500">({totalDocs}/{MAX_FILES})</span>
          </label>
          <input ref={fileRef} type="file" multiple accept=".pdf" onChange={(e) => { void handleFilesPicked(e.target.files); e.target.value = ""; }} className="hidden" />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={totalDocs >= MAX_FILES || (!editMode && !name.trim())}
            className="inline-flex items-center gap-1.5 rounded-lg bg-orange-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-orange-600 disabled:opacity-40 transition-colors"
            title={!editMode && !name.trim() ? "Enter a product name first" : undefined}
          >
            <FileUp className="h-3.5 w-3.5" />
            Add PDF
          </button>
        </div>

        <div className="rounded-lg border border-gray-200 bg-gray-50/50 dark:border-neutral-700 dark:bg-neutral-800/50">
          {totalDocs === 0 && uploadingCount === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-gray-400 dark:text-neutral-500">
              {!editMode && !name.trim()
                ? "Enter a product name above to start adding manuals."
                : "No manuals attached yet. Add PDFs to enable AI-powered Q&A."}
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-neutral-700">
              {/* Edit mode: backend-confirmed sources */}
              {editMode && existingSources.map((source) => (
                <div key={source.id} className="flex items-center justify-between px-3 py-2.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 shrink-0 text-orange-400" />
                    <div className="min-w-0">
                      <span className="block truncate text-xs font-medium text-gray-700 dark:text-neutral-200">{source.label || source.id}</span>
                      {source.pages && <span className="text-[10px] text-gray-400 dark:text-neutral-500">{source.pages} pages</span>}
                    </div>
                  </div>
                  <button type="button" onClick={() => void handleDeleteExisting(source.id)} disabled={deletingId === source.id} className="ml-2 shrink-0 text-gray-300 hover:text-red-500 disabled:opacity-50 dark:text-neutral-600 dark:hover:text-red-400 transition-colors" title="Remove">
                    {deletingId === source.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                  </button>
                </div>
              ))}

              {/* Edit mode: files currently uploading or failed */}
              {editMode && [...fileStatuses.entries()].map(([fileName, status]) => {
                if (status === "done") return null;
                return (
                  <div key={`s-${fileName}`} className="flex items-center justify-between px-3 py-2.5">
                    <div className="flex items-center gap-2 min-w-0">
                      {status === "uploading"
                        ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-orange-400" />
                        : <X className="h-4 w-4 shrink-0 text-red-400" />}
                      <span className="block truncate text-xs text-gray-500 dark:text-neutral-400">{fileName}</span>
                    </div>
                    <span className={`text-[10px] font-medium ${status === "uploading" ? "text-orange-500" : "text-red-500"}`}>
                      {status === "uploading" ? "uploading..." : "failed"}
                    </span>
                  </div>
                );
              })}

              {/* Create mode: locally queued files */}
              {!editMode && pendingFiles.map((f) => (
                <div key={`p-${f.name}`} className="flex items-center justify-between px-3 py-2.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileUp className="h-4 w-4 shrink-0 text-blue-400" />
                    <span className="block truncate text-xs text-gray-600 dark:text-neutral-300">{f.name}</span>
                  </div>
                  <button type="button" onClick={() => removePendingFile(f.name)} className="ml-2 shrink-0 text-gray-300 hover:text-red-500 dark:text-neutral-600 dark:hover:text-red-400 transition-colors">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Processing status (edit mode, informational only - processing is automatic) */}
      {editMode && existingSources.length > 0 && !isUploading && (isProcessing || isReady) && (
        <div className="rounded-lg border border-gray-200 bg-white p-3 dark:border-neutral-700 dark:bg-neutral-800">
          {isProcessing ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-orange-500" />
              <span className="text-xs font-medium text-orange-600 dark:text-orange-400">Processing documents...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-xs font-medium text-green-600 dark:text-green-400">Documents processed and ready for Q&A</span>
            </div>
          )}
        </div>
      )}

      {/* Delete (edit mode only) */}
      {editMode && initialData && !confirmDelete && (
        <div className="border-t border-gray-200 pt-4 dark:border-neutral-700">
          <button type="button" onClick={() => setConfirmDelete(true)} className="text-xs text-red-500 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors">
            Delete this product and all its data
          </button>
        </div>
      )}
      {editMode && confirmDelete && initialData && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/50">
          <p className="text-sm font-medium text-red-700 dark:text-red-300">Are you sure? This will permanently delete:</p>
          <ul className="mt-1.5 text-xs text-red-600 dark:text-red-400 space-y-0.5 list-disc list-inside">
            <li>All uploaded manuals and page images</li>
            <li>All structured data and indexes</li>
            <li>All conversations and chat history</li>
            <li>The product profile itself</li>
          </ul>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={async () => {
                setIsDeleting(true);
                try { await deleteProduct(initialData.id); onDeleted?.(initialData.id); }
                finally { setIsDeleting(false); }
              }}
              disabled={isDeleting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-2 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-60"
            >
              {isDeleting && <Loader2 className="h-3 w-3 animate-spin" />}
              Yes, delete permanently
            </button>
            <button type="button" onClick={() => setConfirmDelete(false)} className="rounded-lg border border-gray-200 px-3 py-2 text-xs text-gray-600 dark:border-neutral-700 dark:text-neutral-300">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center justify-between gap-2 pt-2">
        {/* Submit progress */}
        <div className="min-w-0">
          {submitProgress && (
            <span className="inline-flex items-center gap-1.5 text-xs text-orange-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              {submitProgress}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onClose} disabled={isSubmitting || isUploading} className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={isSubmitting || !name.trim() || isUploading}
            className="inline-flex items-center gap-2 rounded-lg bg-orange-500 px-4 py-2.5 text-sm font-medium text-white hover:bg-orange-600 disabled:opacity-60"
          >
            {isSubmitting && <Loader2 suppressHydrationWarning className="h-4 w-4 animate-spin" />}
            {editMode ? "Save changes" : "Create workspace"}
          </button>
        </div>
      </div>
    </DialogShell>
  );
}
