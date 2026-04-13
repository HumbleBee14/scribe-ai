/** SSE event types from the backend agent. */

export interface TextDeltaEvent {
  event: "text_delta";
  data: { content: string };
}

export interface ToolStartEvent {
  event: "tool_start";
  data: { tool: string; input: Record<string, unknown>; label: string };
}

export interface ToolEndEvent {
  event: "tool_end";
  data: { tool: string; label: string; ok: boolean };
}

export interface ArtifactEvent {
  event: "artifact";
  data: {
    id: string;
    renderer: string;  // mermaid, svg, html, table
    title: string;
    code: string;
    source_pages: Array<{ page: number; description: string }>;
    /** @deprecated Use renderer instead. Kept for backwards compatibility. */
    type?: string;
  };
}

export interface SourcePageRef {
  page: number;
  description: string;
}

export interface ImageEvent {
  event: "image";
  data: {
    page: number;
    url: string;
    product_id?: string;
    source_id?: string | null;
  };
}

export interface ClarificationEvent {
  event: "clarification";
  data: { question: string; options?: string[] };
}

export interface SafetyWarningEvent {
  event: "safety_warning";
  data: { level: "warning" | "danger" | "caution"; content: string };
}

export interface SessionUpdateEvent {
  event: "session_update";
  data: {
    id: string;
    product_id?: string;
  };
}

export interface DoneEvent {
  event: "done";
  data: {
    status: "completed" | "clarification_required";
    usage?: { input_tokens: number; output_tokens: number };
    turns?: number;
  };
}

export interface ErrorEvent {
  event: "error";
  data: { message: string };
}

export type SSEEvent =
  | TextDeltaEvent
  | ToolStartEvent
  | ToolEndEvent
  | ArtifactEvent
  | ImageEvent
  | ClarificationEvent
  | SafetyWarningEvent
  | SessionUpdateEvent
  | DoneEvent
  | ErrorEvent;

/** An ordered content block in an assistant message. */
export type ContentBlock =
  | { type: "text"; text: string }
  | { type: "image"; data: ImageEvent["data"] }
  | { type: "artifact"; data: ArtifactEvent["data"] };

/** Chat message stored in frontend state. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  images?: Array<{ mediaType: string; data: string }>;
  toolCalls?: Array<{ tool: string; label: string; ok?: boolean }>;
  thinking?: string;
  pageImages?: Array<ImageEvent["data"]>;
  safetyWarnings?: Array<SafetyWarningEvent["data"]>;
  clarification?: ClarificationEvent["data"];
  isStreaming?: boolean;
  /** Ordered content blocks for interleaved rendering. */
  blocks?: ContentBlock[];
  /** Follow-up suggestions from the agent. */
  followUps?: string[];
  /** Paths to user-uploaded images (stored on disk, not base64). */
  uploadedImagePaths?: string[];
}

export interface SessionState {
  id: string;
  productId?: string;
}

export interface SelectedSourcePage {
  page: number;
  /** Additional pages to show (for ranges like "pages 35-40"). */
  pages?: number[];
  sourceId?: string | null;
  title?: string;
  description?: string;
}
