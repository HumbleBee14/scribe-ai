"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  code: string;
  title?: string;
}

export function HTMLViewer({ code, title }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(300);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Listen for height messages from the iframe content
    const handleMessage = (event: MessageEvent) => {
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

  // Wrap the HTML with a dark theme base and ResizeObserver
  const wrappedHtml = `
<!DOCTYPE html>
<html>
<head>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0a0a0a;
      color: #ededed;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      padding: 16px;
    }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #333; padding: 8px 12px; text-align: left; }
    th { background: #1a1a2e; color: #f97316; font-weight: 600; }
    tr:nth-child(even) { background: #111; }
    a { color: #f97316; }
    code { background: #1a1a2e; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
    pre { background: #111; border: 1px solid #333; border-radius: 8px; padding: 12px; overflow-x: auto; }
    h1, h2, h3 { color: #fff; margin-bottom: 8px; }
    p { margin-bottom: 8px; line-height: 1.6; }
    button {
      background: #f97316; color: #fff; border: none; padding: 8px 16px;
      border-radius: 8px; cursor: pointer; font-size: 14px;
    }
    button:hover { background: #ea580c; }
    .warning { background: #422006; border: 1px solid #92400e; color: #fbbf24; padding: 12px; border-radius: 8px; }
    .danger { background: #450a0a; border: 1px solid #991b1b; color: #fca5a5; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  ${code}
  <script>
    // Report height to parent for auto-sizing
    const ro = new ResizeObserver(() => {
      window.parent.postMessage(
        { type: 'resize', height: document.body.scrollHeight },
        '*'
      );
    });
    ro.observe(document.body);
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
      <iframe
        ref={iframeRef}
        sandbox="allow-scripts"
        srcDoc={wrappedHtml}
        className="w-full border-0"
        style={{ height: `${height}px` }}
        title={title || "Interactive content"}
      />
    </div>
  );
}
