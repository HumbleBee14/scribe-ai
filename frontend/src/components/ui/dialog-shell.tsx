"use client";

import { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";
import type { ReactNode } from "react";

interface DialogShellProps {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  sizeClassName?: string;
  panelClassName?: string;
  contentClassName?: string;
}

export function DialogShell({
  title,
  subtitle,
  onClose,
  children,
  sizeClassName = "max-w-4xl",
  panelClassName = "",
  contentClassName = "flex-1 overflow-auto",
}: DialogShellProps) {
  const titleId = useId();
  const descriptionId = useId();
  const containerRef = useRef<HTMLDivElement>(null);

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousActive = document.activeElement as HTMLElement | null;
    containerRef.current?.focus();
    document.body.style.overflow = "hidden";

    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
      if (event.key === "Tab" && containerRef.current) {
        const focusables = containerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, textarea, select, [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement;

        if (event.shiftKey && active === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && active === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
      previousActive?.focus();
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-3 sm:p-6"
      onClick={onClose}
    >
      <div
        ref={containerRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? descriptionId : undefined}
        tabIndex={-1}
        className={`relative w-full ${sizeClassName} max-h-[92vh] flex flex-col rounded-2xl bg-white dark:bg-neutral-900 shadow-2xl border border-gray-200 dark:border-neutral-700 overflow-hidden outline-none ${panelClassName}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-200 dark:border-neutral-700 px-4 sm:px-6 py-3 shrink-0">
          <div className="min-w-0">
            <h3
              id={titleId}
              className="text-sm font-semibold text-gray-900 dark:text-neutral-100 truncate"
            >
              {title}
            </h3>
            {subtitle && (
              <p
                id={descriptionId}
                className="text-xs text-gray-400 dark:text-neutral-400 truncate"
              >
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:text-gray-700 dark:text-neutral-400 dark:hover:text-neutral-200 hover:bg-gray-100 dark:hover:bg-neutral-800 transition-colors"
            aria-label="Close dialog"
          >
            <X suppressHydrationWarning className="h-4 w-4" />
          </button>
        </div>
        <div className={contentClassName}>{children}</div>
      </div>
    </div>
  );
}
