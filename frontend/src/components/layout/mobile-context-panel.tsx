"use client";

import { DialogShell } from "@/components/ui/dialog-shell";
import { SourceViewer } from "@/components/evidence/source-viewer";
import type { ArtifactEvent, SelectedSourcePage } from "@/types/events";

interface MobileContextPanelProps {
  open: boolean;
  onClose: () => void;
  productId: string;
  productName: string;
  productDescription: string;
  documentCount: number;
  ingestionLabel: string;
  selectedSource: SelectedSourcePage | null;
  artifacts: ArtifactEvent["data"][];
}

export function MobileContextPanel({
  open,
  onClose,
  productId,
  productName,
  productDescription,
  documentCount,
  ingestionLabel,
  selectedSource,
  artifacts,
}: MobileContextPanelProps) {
  if (!open) return null;

  return (
    <DialogShell
      title="Conversation context"
      subtitle="Workspace, sources, and artifacts"
      onClose={onClose}
      sizeClassName="max-w-2xl"
      contentClassName="p-4 space-y-5 bg-gray-50 dark:bg-neutral-950"
    >
      <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-neutral-700 dark:bg-neutral-900">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-neutral-500">
          Product workspace
        </p>
        <h2 className="mt-1 text-base font-semibold text-gray-900 dark:text-neutral-100">{productName}</h2>
        <p className="mt-2 text-sm leading-snug text-gray-600 dark:text-neutral-400">{productDescription || "Manual assistant workspace"}</p>
        <p className="mt-3 text-xs text-gray-500 dark:text-neutral-500">
          {documentCount} {documentCount === 1 ? "manual" : "manuals"}
          <span className="mx-2 text-gray-300 dark:text-neutral-600" aria-hidden>
            ·
          </span>
          <span className="font-medium text-gray-700 dark:text-neutral-300">{ingestionLabel}</span>
        </p>
      </div>
      <SourceViewer
        productId={productId}
        selectedSource={selectedSource}
        artifacts={artifacts}
      />
    </DialogShell>
  );
}
