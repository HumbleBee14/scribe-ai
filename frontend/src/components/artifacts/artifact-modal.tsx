"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { MermaidViewer } from "./mermaid-viewer";
import { SVGViewer } from "./svg-viewer";
import { HTMLViewer } from "./html-viewer";

interface ArtifactModalProps {
  type: string;
  title: string;
  code: string;
  onClose: () => void;
}

/** Render artifact content directly by type. Reused by modal and inline views. */
export function renderArtifactByType(type: string, code: string, title?: string) {
  if (type === "mermaid") return <MermaidViewer code={code} title={title} />;
  if (type === "svg") return <SVGViewer code={code} title={title} />;
  if (type === "html" || type === "table") return <HTMLViewer code={code} title={title} />;
  return (
    <pre className="p-4 text-xs text-gray-700 dark:text-neutral-300 overflow-auto bg-gray-50 dark:bg-neutral-950 rounded-xl">
      <code>{code.slice(0, 2000)}</code>
    </pre>
  );
}

/** Shared fullscreen artifact modal used by both inline chat artifacts and sidebar. */
export function ArtifactModal({ type, title, code, onClose }: ArtifactModalProps) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-3 sm:p-6"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-5xl h-[90vh] flex flex-col rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl border border-gray-200 dark:border-neutral-700 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-4 sm:px-6 py-3 shrink-0">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 dark:text-neutral-100 truncate">{title}</h3>
            <p className="text-xs text-gray-400 dark:text-neutral-500 uppercase">{type}</p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 dark:text-neutral-500 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 min-h-0 bg-gray-50 dark:bg-neutral-950 [&>div]:h-full [&>div]:!rounded-none [&>div]:!border-0 [&_iframe]:!h-full">
          {renderArtifactByType(type, code, title)}
        </div>
      </div>
    </div>
  );
}
