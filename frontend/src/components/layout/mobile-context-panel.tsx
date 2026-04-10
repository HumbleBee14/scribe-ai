"use client";

import { DialogShell } from "@/components/ui/dialog-shell";
import { SessionSidebar } from "@/components/evidence/session-sidebar";
import { SourceViewer } from "@/components/evidence/source-viewer";
import type { ArtifactEvent, SelectedSourcePage, SessionState } from "@/types/events";

interface MobileContextPanelProps {
  open: boolean;
  onClose: () => void;
  session: SessionState | null;
  selectedSource: SelectedSourcePage | null;
  artifacts: ArtifactEvent["data"][];
}

export function MobileContextPanel({
  open,
  onClose,
  session,
  selectedSource,
  artifacts,
}: MobileContextPanelProps) {
  if (!open) return null;

  return (
    <DialogShell
      title="Conversation context"
      subtitle="Session state, sources, and generated artifacts"
      onClose={onClose}
      sizeClassName="max-w-2xl"
      contentClassName="flex-1 overflow-auto p-4 space-y-6 bg-gray-50 dark:bg-neutral-950"
    >
      <SessionSidebar session={session} />
      <SourceViewer selectedSource={selectedSource} artifacts={artifacts} />
    </DialogShell>
  );
}
