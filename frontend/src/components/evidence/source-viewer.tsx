"use client";

import { useEffect, useState } from "react";
import { Expand, FileImage, X } from "lucide-react";
import { getManualPageImageUrl } from "@/lib/api";
import { ArtifactRenderer } from "@/components/artifacts/artifact-renderer";
import type { ArtifactEvent, SelectedSourcePage } from "@/types/events";

interface Props {
  selectedSource: SelectedSourcePage | null;
  artifacts: ArtifactEvent["data"][];
}

export function SourceViewer({ selectedSource, artifacts }: Props) {
  return (
    <div className="mt-6 space-y-4">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-neutral-500">
          Source Viewer
        </h3>
        <p className="mt-2 text-xs text-gray-400 dark:text-neutral-500">
          Select a cited page from a message to preview it here.
        </p>
      </div>

      {selectedSource ? (
        <SourceCard source={selectedSource} />
      ) : (
        <div className="rounded-xl border border-dashed border-gray-200 dark:border-neutral-700 bg-gray-50/40 dark:bg-neutral-900/40 p-4 text-sm text-gray-400 dark:text-neutral-500">
          No source selected yet.
        </div>
      )}

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-neutral-500">
          Artifacts
        </h3>
        {artifacts.length === 0 ? (
          <p className="mt-2 text-xs text-gray-400 dark:text-neutral-500">
            Artifacts will appear here once the assistant generates visuals.
          </p>
        ) : (
          <SidebarArtifactList artifacts={artifacts} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SourceCard: shows the selected source with inline preview + modal
// Designed to handle images now, extensible for PDFs and multi-page docs
// ---------------------------------------------------------------------------

function SourceCard({ source }: { source: SelectedSourcePage }) {
  const [modalOpen, setModalOpen] = useState(false);
  const url = getManualPageImageUrl(source.page);

  return (
    <>
      <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
              {source.title ?? `Page ${source.page}`}
            </div>
            <div className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
              Page {source.page}
              {source.description ? ` \u00B7 ${source.description}` : ""}
            </div>
          </div>
          <button
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-1 text-xs text-orange-500 hover:text-orange-600 dark:text-orange-400 dark:hover:text-orange-300"
            title="Open preview"
          >
            Open
            <Expand className="h-3 w-3" />
          </button>
        </div>

        {/* Thumbnail: click to open preview modal */}
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="mt-3 block w-full"
        >
          <img
            src={url}
            alt={`Page ${source.page}`}
            className="max-h-80 rounded-lg border border-gray-200 dark:border-neutral-700 hover:opacity-90 transition-opacity"
            loading="lazy"
          />
        </button>
      </div>

      {/* Preview modal */}
      {modalOpen && (
        <DocumentPreviewModal
          title={source.title ?? `Page ${source.page}`}
          subtitle={`Page ${source.page}${source.description ? ` \u00B7 ${source.description}` : ""}`}
          url={url}
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
  url,
  onClose,
}: {
  title: string;
  subtitle?: string;
  url: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Detect content type for future extensibility
  const isPdf = url.endsWith(".pdf");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-6"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl border border-gray-200 dark:border-neutral-700 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-6 py-3 shrink-0">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-neutral-100 truncate">
              {title}
            </h3>
            {subtitle && (
              <p className="text-xs text-gray-400 dark:text-neutral-500 truncate">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 dark:text-neutral-500 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto flex items-center justify-center p-6 bg-gray-50 dark:bg-neutral-950">
          {isPdf ? (
            /* PDF: render in iframe (future support) */
            <iframe
              src={url}
              className="w-full h-full min-h-[70vh] rounded-lg border border-gray-200 dark:border-neutral-700"
              title={title}
            />
          ) : (
            /* Image: render with natural sizing */
            <img
              src={url}
              alt={title}
              className="max-w-full max-h-[80vh] object-contain rounded-lg shadow-lg"
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SidebarArtifactList: clickable artifact cards with preview modal
// ---------------------------------------------------------------------------

function SidebarArtifactList({ artifacts }: { artifacts: ArtifactEvent["data"][] }) {
  const [previewArtifact, setPreviewArtifact] = useState<ArtifactEvent["data"] | null>(null);

  useEffect(() => {
    if (!previewArtifact) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPreviewArtifact(null);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [previewArtifact]);

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
              <FileImage className="h-4 w-4 text-orange-500 dark:text-orange-400 shrink-0" />
              <span className="truncate">{artifact.title}</span>
            </div>
            <div className="mt-1 text-xs uppercase tracking-wide text-gray-500 dark:text-neutral-500">
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

      {/* Artifact preview modal */}
      {previewArtifact && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-8"
          onClick={() => setPreviewArtifact(null)}
        >
          <div
            className="relative w-full max-w-5xl max-h-[90vh] overflow-auto rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl border border-gray-200 dark:border-neutral-700"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-6 py-3 rounded-t-2xl">
              <div>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
                  {previewArtifact.title}
                </h3>
                <p className="text-xs text-gray-400 dark:text-neutral-500 uppercase">
                  {previewArtifact.renderer || previewArtifact.type}
                </p>
              </div>
              <button
                onClick={() => setPreviewArtifact(null)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 dark:text-neutral-500 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-6">
              <ArtifactRenderer artifact={previewArtifact} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
