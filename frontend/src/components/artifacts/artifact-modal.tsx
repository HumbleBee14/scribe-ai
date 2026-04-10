"use client";

import { MermaidViewer } from "./mermaid-viewer";
import { SVGViewer } from "./svg-viewer";
import { HTMLViewer } from "./html-viewer";
import { DialogShell } from "@/components/ui/dialog-shell";

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
  return (
    <DialogShell
      title={title}
      subtitle={type.toUpperCase()}
      onClose={onClose}
      sizeClassName="max-w-5xl"
      panelClassName="h-[90vh]"
      contentClassName="flex-1 min-h-0 bg-gray-50 dark:bg-neutral-950 [&>div]:h-full [&>div]:!rounded-none [&>div]:!border-0 [&_iframe]:!h-full"
    >
      {renderArtifactByType(type, code)}
    </DialogShell>
  );
}
