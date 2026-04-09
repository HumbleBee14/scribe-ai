"use client";

import { useMemo } from "react";
import { AlertCircle } from "lucide-react";

interface Props {
  code: string;
  title?: string;
}

export function SVGViewer({ code, title }: Props) {
  // Sanitize: strip any <script> tags from SVG for safety
  const sanitizedSvg = useMemo(() => {
    return code.replace(/<script[\s\S]*?<\/script>/gi, "");
  }, [code]);

  const isValidSvg = sanitizedSvg.includes("<svg");

  return (
    <div className="rounded-xl border border-neutral-700 bg-neutral-900 overflow-hidden">
      {title && (
        <div className="border-b border-neutral-800 px-4 py-2 text-sm font-medium text-white">
          {title}
        </div>
      )}

      {isValidSvg ? (
        <div
          className="flex items-center justify-center p-4 [&_svg]:max-w-full [&_svg]:h-auto"
          dangerouslySetInnerHTML={{ __html: sanitizedSvg }}
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
