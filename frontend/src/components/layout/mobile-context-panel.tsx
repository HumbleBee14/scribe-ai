"use client";

import { DialogShell } from "@/components/ui/dialog-shell";
import { SourceViewer } from "@/components/evidence/source-viewer";
import type { ArtifactEvent, SelectedSourcePage } from "@/types/events";

interface MobileContextPanelProps {
  open: boolean;
  onClose: () => void;
  productId: string;
  selectedSource: SelectedSourcePage | null;
  artifacts: ArtifactEvent["data"][];
}

export function MobileContextPanel({
  open,
  onClose,
  productId,
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
      contentClassName="p-4 space-y-6 bg-gray-50 dark:bg-neutral-950"
    >
      <SourceViewer
        productId={productId}
        selectedSource={selectedSource}
        artifacts={artifacts}
      />
    </DialogShell>
  );
}
