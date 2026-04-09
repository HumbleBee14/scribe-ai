"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  code: string;
  title?: string;
}

/**
 * Renders SVG inside a sandboxed iframe for safety.
 *
 * Never uses dangerouslySetInnerHTML. The iframe sandbox prevents
 * onload handlers, javascript: URLs, foreignObject scripts, and
 * other SVG-based XSS vectors.
 */
export function SVGViewer({ code, title }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(300);

  const isValidSvg = code.includes("<svg");

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!iframeRef.current) return;
      // Only accept messages from our iframe
      if (event.source !== iframeRef.current.contentWindow) return;
      if (
        event.data &&
        typeof event.data === "object" &&
        event.data.type === "resize" &&
        typeof event.data.height === "number"
      ) {
        setHeight(Math.min(event.data.height + 20, 800));
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  const wrappedSvg = `
<!DOCTYPE html>
<html>
<head>
<style>
  body { margin: 0; padding: 16px; background: #0a0a0a; display: flex; align-items: center; justify-content: center; }
  svg { max-width: 100%; height: auto; }
</style>
</head>
<body>
  ${code}
  <script>
    new ResizeObserver(() => {
      window.parent.postMessage({ type: 'resize', height: document.body.scrollHeight }, '*');
    }).observe(document.body);
  </script>
</body>
</html>`;

  return (
    <div className="rounded-xl border border-neutral-700 bg-neutral-900 overflow-hidden">
      {title && (
        <div className="border-b border-neutral-800 px-4 py-2 text-sm font-medium text-white">
          {title}
        </div>
      )}

      {isValidSvg ? (
        <iframe
          ref={iframeRef}
          sandbox="allow-scripts"
          srcDoc={wrappedSvg}
          className="w-full border-0"
          style={{ height: `${height}px` }}
          title={title || "SVG diagram"}
        />
      ) : (
        <div className="p-4">
          <div className="flex items-start gap-2 text-sm text-red-400">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p>Invalid SVG content</p>
              <pre className="mt-2 overflow-x-auto rounded bg-neutral-950 p-2 text-xs text-neutral-400">
                {code.slice(0, 500)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
