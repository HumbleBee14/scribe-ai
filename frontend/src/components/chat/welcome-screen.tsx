"use client";

import { BookOpen, FileText, Flame, HelpCircle, Search, Settings, Wrench } from "lucide-react";
import { buildBackendUrl } from "@/lib/api";

interface Props {
  productName: string;
  productDescription: string;
  logoUrl?: string;
  quickActions: Array<{ label: string; message: string }>;
  onQuickAction: (message: string) => void;
}

const ICONS = [Settings, Flame, Wrench, HelpCircle, BookOpen, Search];
const COLORS = [
  "text-blue-500 dark:text-blue-400",
  "text-purple-500 dark:text-purple-400",
  "text-yellow-500 dark:text-yellow-400",
  "text-green-500 dark:text-green-400",
  "text-orange-500 dark:text-orange-400",
  "text-cyan-500 dark:text-cyan-400",
];

export function WelcomeScreen({
  productName,
  productDescription,
  logoUrl,
  quickActions,
  onQuickAction,
}: Props) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      {logoUrl ? (
        <img
          src={buildBackendUrl(logoUrl)}
          alt={productName}
          className="mb-4 h-24 w-24 rounded-2xl object-contain"
        />
      ) : (
        <div className="mb-4 flex h-24 w-24 items-center justify-center rounded-2xl bg-gray-100 dark:bg-neutral-800">
          <FileText className="h-10 w-10 text-orange-500" />
        </div>
      )}
      <h2 className="text-xl font-semibold text-gray-900 dark:text-neutral-100">
        {productName}
      </h2>
      <p className="mt-2 max-w-md text-sm text-gray-500 dark:text-neutral-400">
        {productDescription}
      </p>

      <div className="mt-8 grid grid-cols-2 gap-3 w-full max-w-md">
        {quickActions.map((action, index) => {
          const Icon = ICONS[index % ICONS.length];
          const color = COLORS[index % COLORS.length];
          return (
          <button
            key={action.label}
            onClick={() => onQuickAction(action.message)}
            className="flex flex-col items-center gap-2 rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-4 text-sm text-gray-700 dark:text-neutral-200 hover:border-orange-300 dark:hover:border-orange-500 transition-colors"
          >
            <Icon suppressHydrationWarning className={`h-5 w-5 ${color}`} />
            <span>{action.label}</span>
          </button>
          );
        })}
      </div>
    </div>
  );
}
