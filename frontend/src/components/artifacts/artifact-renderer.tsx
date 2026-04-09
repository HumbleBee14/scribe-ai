"use client";

import { FileText } from "lucide-react";
import type { ArtifactEvent, SourcePageRef } from "@/types/events";
import { MermaidViewer } from "./mermaid-viewer";
import { SVGViewer } from "./svg-viewer";
import { HTMLViewer } from "./html-viewer";

interface Props {
  artifact: ArtifactEvent["data"];
  onSelectSourcePage?: (source: { page: number; title?: string; description?: string }) => void;
}

export function ArtifactRenderer({ artifact, onSelectSourcePage }: Props) {
  // Use renderer field (canonical), fall back to type (backwards compat)
  const renderer = artifact.renderer || artifact.type || "";
  const { title, code, source_pages } = artifact;

  return (
    <div className="space-y-2">
      {/* Render based on renderer type */}
      {renderer === "mermaid" && <MermaidViewer code={code} title={title} />}

      {renderer === "svg" && <SVGViewer code={code} title={title} />}

      {(renderer === "html" || renderer === "table") && (
        <HTMLViewer code={code} title={title} />
      )}

      {/* Fallback: show code block for unknown renderers */}
      {!["mermaid", "svg", "html", "table"].includes(renderer) && (
        <div className="rounded-xl border border-neutral-700 bg-neutral-900 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-white">{title}</div>
              <div className="mt-1 text-xs uppercase tracking-wide text-neutral-500">
                {renderer}
              </div>
            </div>
            <FileText className="h-4 w-4 shrink-0 text-orange-400" />
          </div>
          <pre className="mt-3 overflow-x-auto rounded-lg border border-neutral-800 bg-neutral-950 p-3 text-xs text-neutral-300">
            <code>{code}</code>
          </pre>
        </div>
      )}

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
              className="rounded-full border border-neutral-700 bg-neutral-800 px-3 py-1 text-xs text-neutral-200 hover:border-orange-500 hover:text-orange-200 transition-colors"
            >
              p.{source.page}
              {source.description ? ` \u00B7 ${source.description}` : ""}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
