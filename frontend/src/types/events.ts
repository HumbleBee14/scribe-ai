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
    type: string;
    title: string;
    code: string;
    source_pages: Array<{ page: number; description: string }>;
  };
}

export interface ImageEvent {
  event: "image";
  data: { page: number; url: string };
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
    current_process: string | null;
    current_voltage: string | null;
    current_material: string | null;
    current_thickness: string | null;
    setup_steps_completed: string[];
    safety_warnings_shown: string[];
    context_summary: string;
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

/** Chat message stored in frontend state. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  images?: Array<{ mediaType: string; data: string }>;
  toolCalls?: Array<{ tool: string; label: string; ok?: boolean }>;
  artifacts?: Array<ArtifactEvent["data"]>;
  pageImages?: Array<ImageEvent["data"]>;
  safetyWarnings?: Array<SafetyWarningEvent["data"]>;
  clarification?: ClarificationEvent["data"];
  isStreaming?: boolean;
}

export interface SessionState {
  id: string;
  currentProcess: string | null;
  currentVoltage: string | null;
  currentMaterial: string | null;
  currentThickness: string | null;
  setupStepsCompleted: string[];
  contextSummary: string;
}
