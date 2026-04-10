"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  code: string;
  title?: string;
}

export function MermaidViewer({ code, title }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(400);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!iframeRef.current) return;
      if (event.source !== iframeRef.current.contentWindow) return;
      if (!event.data || typeof event.data !== "object") return;
      if (event.data.type === "mermaid-resize") {
        setHeight(Math.min(Math.max(event.data.height, 200), 800));
      }
      if (event.data.type === "mermaid-error") {
        setError(event.data.message);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const cleanCode = code
    .replace(/\\n/g, "\n")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
  const escaped = cleanCode
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Simple approach: let SVG use viewBox for auto-scaling, overflow scroll for manual zoom
  const iframeHtml = `<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; overflow: hidden; }
  #viewport {
    width: 100%; height: 100vh; overflow: hidden;
    cursor: grab; position: relative;
  }
  #viewport:active { cursor: grabbing; }
  #diagram {
    transform-origin: 0 0;
    width: 100%; min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 16px;
  }
  #diagram svg { width: 100%; height: auto; max-height: 95vh; }
  .error { color: #f87171; font: 13px system-ui; padding: 16px; }
  .error pre { margin-top: 8px; font-size: 11px; color: #9ca3af; white-space: pre-wrap; }
  .controls {
    position: fixed; bottom: 8px; right: 8px; display: flex; gap: 4px; z-index: 10;
  }
  .controls button {
    background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2);
    color: #94a3b8; border-radius: 6px; width: 30px; height: 30px;
    cursor: pointer; font-size: 15px; display: flex; align-items: center; justify-content: center;
  }
  .controls button:hover { background: rgba(255,255,255,0.2); color: #fff; }
</style>
</head>
<body>
<div id="viewport">
  <div id="diagram"><pre class="mermaid">${escaped}</pre></div>
</div>
<div class="controls">
  <button id="zin" title="Zoom in">+</button>
  <button id="zout" title="Zoom out">-</button>
  <button id="zreset" title="Reset view">&#x21BA;</button>
</div>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs';

mermaid.initialize({
  startOnLoad: false, theme: 'dark',
  themeVariables: {
    primaryColor: '#f97316', primaryTextColor: '#fff', primaryBorderColor: '#f97316',
    lineColor: '#94a3b8', secondaryColor: '#1e293b', tertiaryColor: '#334155',
    background: '#0f172a', mainBkg: '#1e293b', nodeBorder: '#f97316', titleColor: '#fff',
  },
  fontFamily: 'system-ui, sans-serif', fontSize: 13, securityLevel: 'loose',
});

try {
  const el = document.querySelector('.mermaid');
  const { svg } = await mermaid.render('mmd-render-target', el.textContent);
  const container = document.getElementById('diagram');
  container.innerHTML = svg;

  const svgEl = container.querySelector('svg');
  if (svgEl) {
    // Read natural size before we modify anything
    const natW = svgEl.width?.baseVal?.value || svgEl.getBoundingClientRect().width;
    const natH = svgEl.height?.baseVal?.value || svgEl.getBoundingClientRect().height;

    // Set viewBox so SVG scales responsively
    if (!svgEl.getAttribute('viewBox') && natW > 0 && natH > 0) {
      svgEl.setAttribute('viewBox', '0 0 ' + natW + ' ' + natH);
    }
    svgEl.removeAttribute('width');
    svgEl.removeAttribute('height');
    svgEl.style.width = '100%';
    svgEl.style.height = 'auto';
    svgEl.style.maxHeight = '95vh';

    // Tell parent the rendered height
    requestAnimationFrame(() => {
      const rect = svgEl.getBoundingClientRect();
      window.parent.postMessage({ type: 'mermaid-resize', height: Math.ceil(rect.height) + 32 }, '*');
    });
  }

  // Pan and zoom on the diagram container
  const viewport = document.getElementById('viewport');
  const diagram = document.getElementById('diagram');
  let scale = 1, panX = 0, panY = 0, dragging = false, sx = 0, sy = 0;

  function apply() {
    diagram.style.transform = 'translate('+panX+'px,'+panY+'px) scale('+scale+')';
  }

  viewport.addEventListener('wheel', (e) => {
    e.preventDefault();
    const d = e.deltaY > 0 ? 0.9 : 1.1;
    const ns = Math.max(0.1, Math.min(10, scale * d));
    const r = viewport.getBoundingClientRect();
    const mx = e.clientX - r.left, my = e.clientY - r.top;
    panX = mx - (mx - panX) * (ns / scale);
    panY = my - (my - panY) * (ns / scale);
    scale = ns;
    apply();
  }, { passive: false });

  viewport.addEventListener('mousedown', (e) => { dragging = true; sx = e.clientX - panX; sy = e.clientY - panY; });
  viewport.addEventListener('mousemove', (e) => { if (!dragging) return; panX = e.clientX - sx; panY = e.clientY - sy; apply(); });
  viewport.addEventListener('mouseup', () => { dragging = false; });
  viewport.addEventListener('mouseleave', () => { dragging = false; });

  document.getElementById('zin').addEventListener('click', () => { scale = Math.min(10, scale * 1.3); apply(); });
  document.getElementById('zout').addEventListener('click', () => { scale = Math.max(0.1, scale * 0.7); apply(); });
  document.getElementById('zreset').addEventListener('click', () => { scale = 1; panX = 0; panY = 0; apply(); });

} catch (err) {
  document.getElementById('diagram').innerHTML =
    '<div class="error"><strong>Diagram render failed</strong><pre>' +
    (err.message || err) + '</pre></div>';
  window.parent.postMessage({ type: 'mermaid-error', message: err.message || String(err) }, '*');
  window.parent.postMessage({ type: 'mermaid-resize', height: 100 }, '*');
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
          style={{ height: `${height}px` }}
          title={title || "Mermaid diagram"}
        />
      )}
    </div>
  );
}
