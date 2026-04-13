"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  code: string;
  title?: string;
}

export function HTMLViewer({ code, title }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState(400);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Listen for height messages from OUR iframe only (not other frames)
    const handleMessage = (event: MessageEvent) => {
      if (event.source !== iframe.contentWindow) return;
      if (
        event.data &&
        typeof event.data === "object" &&
        event.data.type === "resize" &&
        typeof event.data.height === "number"
      ) {
        setHeight(Math.min(event.data.height + 20, 500));
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  // Minimal wrapper: just box-sizing reset, font, and padding.
  // All visual styling comes from the AI agent's own CSS in the artifact.
  const wrappedHtml = `
<!DOCTYPE html>
<html>
<head>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      padding: 16px;
      background: #fff;
      color: #111;
    }
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
    <div className="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 overflow-hidden">
      {title && (
        <div className="border-b border-gray-200 dark:border-neutral-700 px-4 py-2 text-sm font-medium text-gray-900 dark:text-neutral-100">
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
