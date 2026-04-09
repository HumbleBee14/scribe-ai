"use client";

import { ExternalLink, FileImage } from "lucide-react";
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
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Source Viewer
        </h3>
        <p className="mt-2 text-xs text-neutral-600">
          Select a cited manual page from a message to preview it here.
        </p>
      </div>

      {selectedSource ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-white">
                {selectedSource.title ?? `Manual Page ${selectedSource.page}`}
              </div>
              <div className="mt-1 text-xs text-neutral-400">
                Page {selectedSource.page}
                {selectedSource.description ? ` · ${selectedSource.description}` : ""}
              </div>
            </div>
            <a
              href={getManualPageImageUrl(selectedSource.page)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-orange-300 hover:text-orange-200"
            >
              Open
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>

          <img
            src={getManualPageImageUrl(selectedSource.page)}
            alt={`Manual page ${selectedSource.page}`}
            className="mt-3 max-h-80 rounded-lg border border-neutral-800"
            loading="lazy"
          />
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-neutral-800 bg-neutral-900/40 p-4 text-sm text-neutral-500">
          No source selected yet.
        </div>
      )}

      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Artifacts
        </h3>
        {artifacts.length === 0 ? (
          <p className="mt-2 text-xs text-neutral-600">
            Artifacts will appear here once the assistant generates visuals.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {artifacts.map((artifact) => (
              <div
                key={artifact.id}
                className="rounded-xl border border-neutral-800 bg-neutral-900 p-3"
              >
                <div className="flex items-center gap-2 text-sm font-medium text-white">
                  <FileImage className="h-4 w-4 text-orange-400" />
                  {artifact.title}
                </div>
                <div className="mt-1 text-xs uppercase tracking-wide text-neutral-500">
                  {artifact.type}
                </div>
                {artifact.source_pages.length > 0 && (
                  <div className="mt-2 text-xs text-neutral-400">
                    Grounded in pages{" "}
                    {artifact.source_pages.map((source) => source.page).join(", ")}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
