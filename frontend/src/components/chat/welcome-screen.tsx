"use client";

import { Flame, HelpCircle, Settings, Wrench } from "lucide-react";

interface Props {
  onQuickAction: (message: string) => void;
}

const QUICK_ACTIONS = [
  {
    icon: Settings,
    label: "Set up MIG",
    message: "I want to set up MIG welding. Walk me through it step by step.",
    color: "text-blue-500 dark:text-blue-400",
  },
  {
    icon: Flame,
    label: "Set up TIG",
    message: "I want to set up TIG welding. What do I need to do?",
    color: "text-purple-500 dark:text-purple-400",
  },
  {
    icon: Wrench,
    label: "Troubleshoot",
    message:
      "I'm having a problem with my welder. Can you help me troubleshoot?",
    color: "text-yellow-500 dark:text-yellow-400",
  },
  {
    icon: HelpCircle,
    label: "View specs",
    message: "What are the specifications for all welding processes on this machine?",
    color: "text-green-500 dark:text-green-400",
  },
];

export function WelcomeScreen({ onQuickAction }: Props) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <div className="mb-2 text-4xl">&#x1F525;</div>
      <h2 className="text-xl font-semibold text-gray-900 dark:text-neutral-100">
        Vulcan OmniPro 220 Expert
      </h2>
      <p className="mt-2 max-w-md text-sm text-gray-500 dark:text-neutral-400">
        I can help you set up, operate, and troubleshoot your welder. Ask me
        anything about duty cycles, polarity, wire feed, settings, or upload a
        photo of your weld for diagnosis.
      </p>

      <div className="mt-8 grid grid-cols-2 gap-3 w-full max-w-md">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => onQuickAction(action.message)}
            className="flex flex-col items-center gap-2 rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 p-4 text-sm text-gray-700 dark:text-neutral-200 hover:border-orange-300 dark:hover:border-orange-500 transition-colors"
          >
            <action.icon suppressHydrationWarning className={`h-5 w-5 ${action.color}`} />
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
