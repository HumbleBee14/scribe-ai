/** SSE streaming client for the chat API. */

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function buildBackendUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${BACKEND_URL}${normalizedPath}`;
}

export function getManualPageImageUrl(page: number): string {
  return buildBackendUrl(`/assets/images/page_${String(page).padStart(2, "0")}.png`);
}

export interface ChatRequestPayload {
  session_id: string | null;
  message: string;
  images?: Array<{ media_type: string; data: string }>;
}

/**
 * Stream chat events from the backend via SSE.
 * Yields parsed { event, data } objects as they arrive.
 */
export async function* streamChat(
  payload: ChatRequestPayload,
  signal?: AbortSignal,
): AsyncGenerator<{ event: string; data: Record<string, unknown> }> {
  const response = await fetch(buildBackendUrl("/api/chat/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status} ${response.statusText}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE lines
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        try {
          const data = JSON.parse(line.slice(6));
          yield { event: currentEvent, data };
        } catch {
          // Skip malformed JSON
        }
        currentEvent = "";
      }
    }
  }
}

/** Fetch session state from the backend. */
export async function getSession(
  sessionId: string
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(buildBackendUrl(`/api/chat/session/${sessionId}`));
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
