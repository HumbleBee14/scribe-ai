"use client";

import { useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

function subscribe() {
  return () => {};
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const mounted = useSyncExternalStore(subscribe, () => true, () => false);

  return (
    <button
      type="button"
      onClick={toggle}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-gray-500 dark:text-neutral-400 hover:text-gray-900 dark:hover:text-neutral-100 transition-colors"
      title={
        !mounted
          ? "Toggle theme"
          : theme === "light"
            ? "Switch to dark mode"
            : "Switch to light mode"
      }
    >
      {!mounted || theme === "light" ? (
        <Moon suppressHydrationWarning className="h-4 w-4" />
      ) : (
        <Sun suppressHydrationWarning className="h-4 w-4" />
      )}
    </button>
  );
}
