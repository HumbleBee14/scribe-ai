"use client";

import { Activity, Gauge, Layers, Zap } from "lucide-react";
import type { SessionState } from "@/types/events";

interface Props {
  session: SessionState | null;
}

export function SessionSidebar({ session }: Props) {
  if (!session) return null;

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
    </div>
  );
}
