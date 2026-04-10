"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  code: string;
  title?: string;
}

/**
 * Renders Mermaid diagrams safely inside an iframe to avoid:
 * 1. React removeChild errors (Mermaid manipulates DOM directly)
 * 2. Mermaid error elements leaking into the page layout
 *
 * The iframe isolates Mermaid's DOM mutations from React entirely.
 */
export function MermaidViewer({ code, title }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(300);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!iframeRef.current) return;
      if (event.source !== iframeRef.current.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;

      if (event.data.type === "mermaid-resize" && typeof event.data.height === "number") {
        setHeight(Math.min(Math.max(event.data.height + 20, 100), 800));
      }
      if (event.data.type === "mermaid-error" && typeof event.data.message === "string") {
        setError(event.data.message);
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Sanitize Mermaid code: replace literal \n with newlines, strip problematic chars
  const cleanCode = code
    .replace(/\\n/g, "\n")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");

  const iframeHtml = `
<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    min-height: 50px;
  }
  .mermaid svg { max-width: 100%; height: auto; }
  .error-container {
    color: #dc2626;
    font-family: system-ui, sans-serif;
    font-size: 13px;
    padding: 12px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    max-width: 100%;
    overflow: auto;
  }
  .error-container pre {
    margin-top: 8px;
    font-size: 11px;
    color: #6b7280;
    white-space: pre-wrap;
    word-break: break-all;
  }
</style>
</head>
<body>
<div class="mermaid">${cleanCode.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';

  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    themeVariables: {
      primaryColor: '#f97316',
      primaryTextColor: '#fff',
      primaryBorderColor: '#f97316',
      lineColor: '#666',
      secondaryColor: '#1a1a2e',
      tertiaryColor: '#2a2a3e',
      background: '#0f172a',
      mainBkg: '#1a1a2e',
      nodeBorder: '#f97316',
      titleColor: '#fff',
    },
    fontFamily: 'system-ui, sans-serif',
    fontSize: 13,
    securityLevel: 'loose',
  });

  try {
    const el = document.querySelector('.mermaid');
    const { svg } = await mermaid.render('mermaid-diagram', el.textContent);
    el.innerHTML = svg;
    // Report height to parent
    requestAnimationFrame(() => {
      window.parent.postMessage(
        { type: 'mermaid-resize', height: document.body.scrollHeight },
        '*'
      );
    });
  } catch (err) {
    const el = document.querySelector('.mermaid');
    el.innerHTML = '<div class="error-container">'
      + '<strong>Failed to render Mermaid diagram</strong>'
      + '<pre>' + (err.message || err) + '</pre>'
      + '</div>';
    window.parent.postMessage(
      { type: 'mermaid-error', message: err.message || String(err) },
      '*'
    );
    requestAnimationFrame(() => {
      window.parent.postMessage(
        { type: 'mermaid-resize', height: document.body.scrollHeight },
        '*'
      );
    });
  }
</script>
</body>
</html>`;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 overflow-hidden">
      {title && (
        <div className="border-b border-gray-200 dark:border-neutral-700 px-4 py-2 text-sm font-medium text-gray-900 dark:text-neutral-100">
          {title}
        </div>
      )}

      {error ? (
        <div className="p-4">
          <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p>Failed to render diagram</p>
              <pre className="mt-2 overflow-x-auto rounded bg-gray-50 dark:bg-neutral-950 p-2 text-xs text-gray-500 dark:text-neutral-400 max-h-40 overflow-y-auto">
                {cleanCode.slice(0, 500)}
              </pre>
            </div>
          </div>
        </div>
      ) : (
        <iframe
          ref={iframeRef}
          sandbox="allow-scripts"
          srcDoc={iframeHtml}
          className="w-full border-0"
          style={{ height: `${height}px`, background: "transparent" }}
          title={title || "Mermaid diagram"}
        />
      )}
    </div>
  );
}
