"use client";

import { Activity, Gauge, Layers, Zap } from "lucide-react";
import type { SessionState } from "@/types/events";

interface Props {
  session: SessionState | null;
}

export function SessionSidebar({ session }: Props) {
  if (!session) {
    return (
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
          Session Context
        </h3>
        <p className="text-xs text-neutral-600">
          Start a conversation and the assistant will track your current process,
          voltage, material, and setup state here.
        </p>
      </div>
    );
  }

  const items = [
    {
      icon: Zap,
      label: "Process",
      value: session.currentProcess?.replace("_", "-") ?? "Not set",
      active: !!session.currentProcess,
    },
    {
      icon: Gauge,
      label: "Voltage",
      value: session.currentVoltage?.toUpperCase() ?? "Not set",
      active: !!session.currentVoltage,
    },
    {
      icon: Layers,
      label: "Material",
      value: session.currentMaterial?.replace("_", " ") ?? "Not set",
      active: !!session.currentMaterial,
    },
    {
      icon: Activity,
      label: "Thickness",
      value: session.currentThickness ?? "Not set",
      active: !!session.currentThickness,
    },
  ];

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
        Session Context
      </h3>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-2">
          <item.icon
            className={`h-4 w-4 ${
              item.active ? "text-orange-400" : "text-neutral-600"
            }`}
          />
          <div className="min-w-0">
            <div className="text-[10px] uppercase text-neutral-500">
              {item.label}
            </div>
            <div
              className={`text-xs truncate ${
                item.active ? "text-neutral-200" : "text-neutral-600"
              }`}
            >
              {item.value}
            </div>
          </div>
        </div>
      ))}

      {session.setupStepsCompleted.length > 0 && (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
          <div className="text-[10px] uppercase text-neutral-500">Setup Steps</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {session.setupStepsCompleted.map((step) => (
              <span
                key={step}
                className="rounded-full bg-neutral-800 px-2 py-1 text-[11px] text-neutral-200"
              >
                {step}
              </span>
            ))}
          </div>
        </div>
      )}

      {session.safetyWarningsShown.length > 0 && (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
          <div className="text-[10px] uppercase text-neutral-500">Safety Topics</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {session.safetyWarningsShown.map((warning) => (
              <span
                key={warning}
                className="rounded-full bg-red-950 px-2 py-1 text-[11px] text-red-200"
              >
                {warning.replace("_", " ")}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
