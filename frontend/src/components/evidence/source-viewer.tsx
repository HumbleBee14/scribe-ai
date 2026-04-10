"use client";

import { useEffect, useState } from "react";
import { ExternalLink, FileImage, X } from "lucide-react";
import { ArtifactRenderer } from "@/components/artifacts/artifact-renderer";
import { getManualPageImageUrl } from "@/lib/api";
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
          Select a cited manual page from a message to preview it here.
        </p>
      </div>

      {selectedSource ? (
        <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-gray-900 dark:text-neutral-100">
                {selectedSource.title ?? `Manual Page ${selectedSource.page}`}
              </div>
              <div className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
                Page {selectedSource.page}
                {selectedSource.description ? ` · ${selectedSource.description}` : ""}
              </div>
            </div>
            <a
              href={getManualPageImageUrl(selectedSource.page)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-orange-500 hover:text-orange-600 dark:text-orange-400 dark:hover:text-orange-300"
            >
              Open
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          <img
            src={getManualPageImageUrl(selectedSource.page)}
            alt={`Manual page ${selectedSource.page}`}
            className="mt-3 max-h-80 rounded-lg border border-gray-200 dark:border-neutral-700"
            loading="lazy"
          />
        </div>
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

      {/* Preview modal */}
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
