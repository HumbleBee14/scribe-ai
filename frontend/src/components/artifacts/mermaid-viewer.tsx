"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  code: string;
  title?: string;
}

export function MermaidViewer({ code, title }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [rendered, setRendered] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      if (!containerRef.current || !code.trim()) return;

      try {
        // Dynamic import to avoid SSR issues (mermaid needs DOM)
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          themeVariables: {
            primaryColor: "#f97316",
            primaryTextColor: "#fff",
            primaryBorderColor: "#f97316",
            lineColor: "#666",
            secondaryColor: "#1a1a2e",
            tertiaryColor: "#2a2a3e",
            background: "#0a0a0a",
            mainBkg: "#1a1a2e",
            nodeBorder: "#f97316",
            clusterBkg: "#1a1a2e",
            titleColor: "#fff",
            edgeLabelBackground: "#1a1a2e",
          },
          fontFamily: "inherit",
          fontSize: 14,
        });

        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, code.trim());

        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setRendered(true);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to render diagram"
          );
          setRendered(false);
        }
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [code]);

  return (
    <div className="rounded-xl border border-neutral-700 bg-neutral-900 overflow-hidden">
      {title && (
        <div className="border-b border-neutral-800 px-4 py-2 text-sm font-medium text-white">
          {title}
        </div>
      )}

      {error ? (
        <div className="p-4">
          <div className="flex items-start gap-2 text-sm text-red-400">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p>Failed to render Mermaid diagram</p>
              <pre className="mt-2 overflow-x-auto rounded bg-neutral-950 p-2 text-xs text-neutral-400">
                {code}
              </pre>
            </div>
          </div>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="flex items-center justify-center p-4 [&_svg]:max-w-full"
        >
          {!rendered && (
            <div className="text-sm text-neutral-500">Rendering diagram...</div>
          )}
        </div>
      )}
    </div>
  );
}
