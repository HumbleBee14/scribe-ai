"use client";

import { useState } from "react";
import Image from "next/image";
import { Expand, FileImage } from "lucide-react";
import { getManualPageImageUrl } from "@/lib/api";
import { ArtifactModal } from "@/components/artifacts/artifact-modal";
import { DialogShell } from "@/components/ui/dialog-shell";
import type { ArtifactEvent, SelectedSourcePage } from "@/types/events";

interface Props {
  productId: string;
  selectedSource: SelectedSourcePage | null;
  artifacts: ArtifactEvent["data"][];
}

export function SourceViewer({ productId, selectedSource, artifacts }: Props) {
  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-neutral-400">
          Artifacts
        </h3>
        {artifacts.length === 0 ? (
          <p className="mt-2 text-xs text-gray-400 dark:text-neutral-400">
            Artifacts will appear here once the assistant generates visuals.
          </p>
        ) : (
          <SidebarArtifactList artifacts={artifacts} />
        )}
      </div>

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-neutral-400">
          Source Viewer
        </h3>
        <p className="mt-2 text-xs text-gray-400 dark:text-neutral-400">
          Select a cited page from a message to preview it here.
        </p>
      </div>

      {selectedSource ? (
        <SourceCard productId={productId} source={selectedSource} />
      ) : (
        <div className="rounded-xl border border-dashed border-gray-200 dark:border-neutral-700 bg-gray-50/40 dark:bg-neutral-900/40 p-4 text-sm text-gray-400 dark:text-neutral-400">
          No source selected yet.
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SourceCard: shows the selected source with inline preview + modal
// Designed to handle images now, extensible for PDFs and multi-page docs
// ---------------------------------------------------------------------------

function SourceCard({
  productId,
  source,
}: {
  productId: string;
  source: SelectedSourcePage;
}) {
  const [modalOpen, setModalOpen] = useState(false);

  // All pages to show (single page or range)
  const pages = source.pages && source.pages.length > 1
    ? source.pages
    : [source.page];

  return (
    <>
      <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
              {source.title ?? `Page ${source.page}`}
            </div>
            <div className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
              {pages.length > 1 ? `Pages ${pages[0]}-${pages[pages.length - 1]}` : `Page ${source.page}`}
              {source.description ? ` \u00B7 ${source.description}` : ""}
            </div>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-1 text-xs text-orange-500 hover:text-orange-600 dark:text-orange-400 dark:hover:text-orange-300"
            title="Open preview"
          >
            Open
            <Expand suppressHydrationWarning className="h-3 w-3" />
          </button>
        </div>

        {/* Scrollable page thumbnails */}
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="mt-3 block w-full"
        >
          <div className={`${pages.length > 1 ? "max-h-60 overflow-y-auto space-y-2 rounded-lg" : ""}`}>
            {pages.map((p) => (
              <div key={p} className="relative">
                {pages.length > 1 && (
                  <div className="absolute top-1 left-1 rounded bg-black/50 px-1.5 py-0.5 text-[10px] text-white font-medium">
                    p.{p}
                  </div>
                )}
                <Image
                  src={getManualPageImageUrl(productId, p, source.sourceId ?? "default")}
                  alt={`Page ${p}`}
                  unoptimized
                  width={1200}
                  height={1600}
                  className="w-full rounded-lg border border-gray-200 dark:border-neutral-700 hover:opacity-90 transition-opacity"
                />
              </div>
            ))}
          </div>
        </button>
      </div>

      {/* Preview modal: scrollable stack of all pages */}
      {modalOpen && (
        <DocumentPreviewModal
          title={source.title ?? `Page ${source.page}`}
          subtitle={
            pages.length > 1
              ? `Pages ${pages[0]}-${pages[pages.length - 1]}${source.description ? ` \u00B7 ${source.description}` : ""}`
              : `Page ${source.page}${source.description ? ` \u00B7 ${source.description}` : ""}`
          }
          pages={pages}
          productId={productId}
          sourceId={source.sourceId ?? "default"}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// DocumentPreviewModal: general-purpose document/page preview
// Currently renders images. Extensible for PDFs (iframe with pdf viewer),
// multi-page navigation, or any document type.
// ---------------------------------------------------------------------------

function DocumentPreviewModal({
  title,
  subtitle,
  pages,
  productId,
  sourceId,
  onClose,
}: {
  title: string;
  subtitle?: string;
  /** Page numbers to render. Single page or a range. */
  pages: number[];
  productId: string;
  sourceId: string;
  onClose: () => void;
}) {
  return (
    <DialogShell
      title={title}
      subtitle={subtitle}
      onClose={onClose}
      sizeClassName="max-w-4xl"
      contentClassName="p-6 bg-gray-50 dark:bg-neutral-950"
    >
      <div className={`${pages.length > 1 ? "space-y-4" : "flex items-center justify-center min-h-full"}`}>
        {pages.map((p) => (
          <div key={p} className="relative">
            {pages.length > 1 && (
              <div className="sticky top-0 z-10 mb-2 inline-block rounded-full bg-gray-200 dark:bg-neutral-700 px-2.5 py-1 text-xs font-medium text-gray-600 dark:text-neutral-300">
                Page {p}
              </div>
            )}
            <Image
              src={getManualPageImageUrl(productId, p, sourceId)}
              alt={`Page ${p}`}
              unoptimized
              width={1400}
              height={1800}
              className="max-w-full object-contain rounded-lg shadow-lg"
            />
          </div>
        ))}
      </div>
    </DialogShell>
  );
}

// ---------------------------------------------------------------------------
// SidebarArtifactList: clickable artifact cards with preview modal
// ---------------------------------------------------------------------------

function SidebarArtifactList({ artifacts }: { artifacts: ArtifactEvent["data"][] }) {
  const [previewArtifact, setPreviewArtifact] = useState<ArtifactEvent["data"] | null>(null);

  return (
    <>
      <div className="mt-3 space-y-3">
        {artifacts.map((artifact) => (
          <button
            key={artifact.id}
            type="button"
            onClick={() => setPreviewArtifact(artifact)}
            className="w-full text-left rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-3 hover:border-orange-300 dark:hover:border-orange-500 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-2 text-sm font-medium text-gray-900 dark:text-neutral-100">
              <FileImage suppressHydrationWarning className="h-4 w-4 text-orange-500 dark:text-orange-400 shrink-0" />
              <span className="truncate">{artifact.title}</span>
            </div>
            <div className="mt-1 text-xs uppercase tracking-wide text-gray-500 dark:text-neutral-400">
              {artifact.renderer || artifact.type}
            </div>
            {artifact.source_pages.length > 0 && (
              <div className="mt-2 text-xs text-gray-500 dark:text-neutral-400">
                Grounded in pages{" "}
                {artifact.source_pages.map((s) => s.page).join(", ")}
              </div>
            )}
          </button>
        ))}
      </div>

      {previewArtifact && (
        <ArtifactModal
          type={previewArtifact.renderer || previewArtifact.type || ""}
          title={previewArtifact.title}
          code={previewArtifact.code}
          onClose={() => setPreviewArtifact(null)}
        />
      )}
    </>
  );
}
