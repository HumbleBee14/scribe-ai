"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  code: string;
  title?: string;
}

// Common emoji to text replacements for Mermaid compatibility
// No emoji stripping -- emojis are preserved via auto-quoting labels.

/**
 * Fix multi-line node labels in Mermaid code.
 * Mermaid does NOT support literal newlines inside node brackets.
 * Claude frequently generates multi-line node text which crashes the parser.
 *
 * Simple approach: join all lines between unmatched open/close brackets.
 * Replace the newlines with <br/> for [] nodes, spaces for {} and () nodes.
 */
function fixMultilineNodes(code: string): string {
  // Join lines that are continuations of unclosed brackets.
  // Track what TYPE of bracket we're inside so we can quote correctly.
  const lines = code.split("\n");
  const output: string[] = [];
  let buffer = "";
  let depth = 0;
  let firstBracket = ""; // the outermost bracket char when multi-line started

  for (const line of lines) {
    if (depth > 0) {
      buffer += "<br/>" + line.trim();
    } else {
      if (buffer) {
        // This buffer was a multi-line node. Quote if the outermost bracket is [
        if (firstBracket === "[" && buffer.includes("<br/>")) {
          // Find the [ that started it and add quotes around content
          buffer = quoteRectangleContent(buffer);
        }
        output.push(buffer);
      }
      buffer = line;
      firstBracket = "";
    }

    for (const ch of line) {
      if (ch === "[" || ch === "{" || ch === "(") {
        if (depth === 0) firstBracket = ch;
        depth++;
      }
      if (ch === "]" || ch === "}" || ch === ")") {
        depth--;
      }
    }
    if (depth < 0) depth = 0;
  }

  // Flush last buffer
  if (buffer) {
    if (firstBracket === "[" && buffer.includes("<br/>")) {
      buffer = quoteRectangleContent(buffer);
    }
    output.push(buffer);
  }

  return output.join("\n");
}

/** Add quotes around the LAST [...] content that contains <br/> in a line. */
function quoteRectangleContent(line: string): string {
  // Find the last [ that opens a multi-line rectangle
  // We need to be careful not to quote ([...]) stadium content
  const lastOpenBracket = line.lastIndexOf("[");
  if (lastOpenBracket < 0) return line;

  // Skip if preceded by ( (stadium shape)
  if (lastOpenBracket > 0 && line[lastOpenBracket - 1] === "(") return line;

  const closeBracket = line.indexOf("]", lastOpenBracket);
  if (closeBracket < 0) return line;

  const before = line.slice(0, lastOpenBracket + 1);
  const content = line.slice(lastOpenBracket + 1, closeBracket);
  const after = line.slice(closeBracket);

  if (!content.includes("<br/>")) return line;

  const cleaned = content.replace(/^"|"$/g, "");
  return before + '"' + cleaned + '"' + after;
}

/** Detect if Mermaid code was truncated (incomplete AI output). */
function detectTruncation(): boolean {
  // Disabled: let Mermaid try to render and show its own error if invalid.
  // The truncation heuristic had too many false positives.
  return false;
}

/**
 * Sanitize Mermaid code so the parser doesn't choke on special characters.
 * - Replaces literal \n with real newlines
 * - Strips control characters
 * - Replaces common emojis with text equivalents
 * - Wraps node labels containing special chars in quotes
 */
/**
 * Auto-quote node labels that contain emoji characters.
 * Mermaid requires quotes around labels with emojis.
 * e.g. A([✅ Found]) -> A(["✅ Found"])
 * Only quotes labels that actually contain emojis -- leaves everything else alone.
 */
/**
 * Auto-quote unquoted node labels that contain emojis or escaped brackets.
 * Already-quoted labels (with ") are left untouched.
 * e.g. {arr\[mid\]} -> {"arr[mid]"}
 * e.g. ([✅ Found]) -> (["✅ Found"])
 * e.g. ["already quoted ✅"] -> unchanged
 */
function quoteLabels(code: string): string {
  return code.split("\n").map(line => {
    // Process each node definition on the line.
    // Match: opening brackets + UNQUOTED content + closing brackets.
    // The key: we skip already-quoted labels by checking for " right after open bracket.
    // Only match node definitions: ID immediately followed by bracket.
    // This skips edge labels like -- "text" --> which are already quoted.
    return line.replace(
      /([a-zA-Z0-9_])(\(\[|\[|\(\(|\(|\{)([^"]*?)(\]\)|\]|\)\)|\)|\})/g,
      (match, id: string, open: string, content: string, close: string) => {
        // Safe: alphanumeric, common punctuation, <br/> tags, math operators
        if (/^[a-zA-Z0-9 _\-?!.,;:'+=%<>\/\n]*(?:<br\/?>)*[a-zA-Z0-9 _\-?!.,;:'+=%<>\/\n]*$/.test(content)) return match;

        // Unescape \[ and \] since they'll be inside quotes now
        let cleaned = content.replace(/\\(\[|\])/g, "$1");
        cleaned = cleaned.replace(/"/g, "'");
        return `${id}${open}"${cleaned}"${close}`;
      }
    );
  }).join("\n");
}

function sanitizeMermaid(raw: string): string {
  let code = (raw || "").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");

  // Normalize \n
  if (!code.includes("\n") && code.includes("\\n")) {
    code = code.replace(/\\n/g, "\n");
  } else if (code.includes("\\n")) {
    code = code.replace(/\\n/g, "\n");
  }

  // Fix multi-line node labels
  code = fixMultilineNodes(code);

  // Normalize common AI syntax mistakes
  code = code.replace(/\[\[(\w)/g, "[($1");       // [[ -> [( subroutine confusion
  code = code.replace(/\/!\\/g, "WARNING:");        // /!\ not valid
  code = code.replace(/─{3,}/g, "---");            // box-drawing dashes
  code = code.replace(/[""]/g, '"');               // smart quotes
  code = code.replace(/['']/g, "'");               // smart single quotes
  code = code.replace(/[\u200B-\u200D\uFEFF]/g, ""); // zero-width junk

  // Fix backslash-escaped quotes inside labels: \" -> ' (Mermaid has no escape syntax)
  // Match content inside ["..."] and replace \" with '
  code = code.replace(/\["((?:[^"]|\\")*)"\]/g, (match) => {
    return match.replace(/\\"/g, "'");
  });

  // Also fix bare \" anywhere else in the code (outside quotes)
  code = code.replace(/\\"/g, "'");

  // Auto-quote labels with special chars (emojis, parens, symbols)
  code = quoteLabels(code);

  return code;
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

  const cleanCode = sanitizeMermaid(code);

  // Detect truncated code (incomplete AI output)
  const isTruncated = detectTruncation();

  const escaped = cleanCode
    .replace(/&/g, "&amp;")
    .replace(/<(?!br\s*\/?>)/gi, "&lt;")
    .replace(/(?<!<br\s*\/?)>/gi, "&gt;");

  // Simple approach: let SVG use viewBox for auto-scaling, overflow scroll for manual zoom
  const iframeHtml = `<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #fff; overflow: hidden; }
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
  /* Hide raw mermaid text until rendered */
  .mermaid { visibility: hidden; position: absolute; }
  .error { color: #f87171; font: 13px system-ui; padding: 16px; }
  .error pre { margin-top: 8px; font-size: 11px; color: #9ca3af; white-space: pre-wrap; }
  .controls {
    position: fixed; bottom: 8px; right: 8px; display: flex; gap: 4px; z-index: 10;
  }
  .controls button {
    background: #f3f4f6; border: 1px solid #d1d5db;
    color: #374151; border-radius: 6px; width: 32px; height: 32px;
    cursor: pointer; font-size: 15px; font-weight: 600;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 1px 2px rgba(0,0,0,0.08);
  }
  .controls button:hover { background: #e5e7eb; color: #111827; }
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
  startOnLoad: false, theme: 'default',
  fontFamily: 'system-ui, sans-serif', fontSize: 13, securityLevel: 'loose',
});

try {
  const el = document.querySelector('.mermaid');
  const raw = el.textContent;
  const { svg } = await mermaid.render('mmd-render-target', raw);
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
        <div className="border-b border-gray-200 dark:border-neutral-700 bg-gray-50 dark:bg-neutral-800 px-4 py-2 text-sm font-medium text-gray-900 dark:text-neutral-100">
          {title}
        </div>
      )}
      {isTruncated ? (
        <div className="p-4">
          <div className="flex items-start gap-2 text-sm text-amber-600 dark:text-amber-400">
            <AlertCircle suppressHydrationWarning className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Diagram was cut off</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-neutral-400">
                The AI response was truncated before the diagram was complete. Ask it to regenerate.
              </p>
            </div>
          </div>
        </div>
      ) : error ? (
        <div className="p-4">
          <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
            <AlertCircle suppressHydrationWarning className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">Failed to render diagram</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-neutral-400">{error}</p>
              <details className="mt-2">
                <summary className="text-xs text-gray-400 cursor-pointer hover:text-gray-600">Show raw code</summary>
                <pre className="mt-1 overflow-x-auto rounded bg-gray-50 dark:bg-neutral-950 p-2 text-xs text-gray-500 dark:text-neutral-400 max-h-40 overflow-y-auto">
                  {cleanCode.slice(0, 1000)}
                </pre>
              </details>
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
