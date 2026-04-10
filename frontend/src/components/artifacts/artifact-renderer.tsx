"use client";

import { useEffect, useState } from "react";
import { Expand, FileText, X } from "lucide-react";
import type { ArtifactEvent, SourcePageRef } from "@/types/events";
import { MermaidViewer } from "./mermaid-viewer";
import { SVGViewer } from "./svg-viewer";
import { HTMLViewer } from "./html-viewer";

interface Props {
  artifact: ArtifactEvent["data"];
  onSelectSourcePage?: (source: { page: number; title?: string; description?: string }) => void;
}

export function ArtifactRenderer({ artifact, onSelectSourcePage }: Props) {
  const renderer = artifact.renderer || artifact.type || "";
  const { title, code, source_pages } = artifact;
  const [zoomed, setZoomed] = useState(false);

  // Close on Escape
  useEffect(() => {
    if (!zoomed) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setZoomed(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [zoomed]);

  const renderContent = (fullWidth?: boolean) => {
    if (renderer === "mermaid") return <MermaidViewer code={code} title={fullWidth ? undefined : title} />;
    if (renderer === "svg") return <SVGViewer code={code} title={fullWidth ? undefined : title} />;
    if (renderer === "html" || renderer === "table") return <HTMLViewer code={code} title={fullWidth ? undefined : title} />;

    return (
      <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-900 dark:text-neutral-100">{title}</div>
            <div className="mt-1 text-xs uppercase tracking-wide text-gray-500 dark:text-neutral-500">{renderer}</div>
          </div>
          <FileText className="h-4 w-4 shrink-0 text-orange-500 dark:text-orange-400" />
        </div>
        <pre className="mt-3 overflow-x-auto rounded-lg border border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-950 p-3 text-xs text-gray-700 dark:text-neutral-300">
          <code>{code}</code>
        </pre>
      </div>
    );
  };

  return (
    <div className="space-y-2">
      {/* Inline artifact with expand button */}
      <div className="relative group">
        {renderContent()}

        {/* Expand/zoom button */}
        <button
          onClick={() => setZoomed(true)}
          className="absolute top-2 right-2 hidden group-hover:flex h-7 w-7 items-center justify-center rounded-lg bg-black/50 text-white hover:bg-black/70 transition-colors"
          title="Expand artifact"
        >
          <Expand className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Source page links */}
      {source_pages.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {source_pages.map((source: SourcePageRef, i: number) => (
            <button
              key={`source-${i}`}
              onClick={() =>
                onSelectSourcePage?.({
                  page: source.page,
                  title,
                  description: source.description,
                })
              }
              className="rounded-full border border-gray-200 dark:border-neutral-700 bg-gray-100 dark:bg-neutral-800 px-3 py-1 text-xs text-gray-700 dark:text-neutral-200 hover:border-orange-300 dark:hover:border-orange-500 hover:text-orange-600 dark:hover:text-orange-200 transition-colors"
            >
              p.{source.page}
              {source.description ? ` \u00B7 ${source.description}` : ""}
            </button>
          ))}
        </div>
      )}

      {/* Zoom modal */}
      {zoomed && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={() => setZoomed(false)}
        >
          <div
            className="relative w-full max-w-6xl max-h-[94vh] flex flex-col rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl border border-gray-200 dark:border-neutral-700 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-6 py-3 shrink-0">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-neutral-100 truncate">{title}</h3>
                <p className="text-xs text-gray-400 dark:text-neutral-500 uppercase">{renderer}</p>
              </div>
              <button
                onClick={() => setZoomed(false)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 dark:text-neutral-500 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Content: scrollable, iframe stretches to fill */}
            <div className="flex-1 overflow-auto min-h-0 bg-gray-50 dark:bg-neutral-950 [&_iframe]:!min-h-[60vh]">
              {renderContent(true)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
