/** SSE streaming client for the chat API. */

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function buildBackendUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${BACKEND_URL}${normalizedPath}`;
}

export function getManualPageImageUrl(
  productId: string,
  page: number,
  sourceId = "owner-manual"
): string {
  return buildBackendUrl(
    `/api/products/${productId}/assets/pages/${sourceId}/page_${String(page).padStart(2, "0")}.png`
  );
}

export interface ProductSourceSummary {
  id: string;
  type: string;
  label: string;
  pages?: number | null;
}

export interface ProductSummary {
  id: string;
  name: string;
  description: string;
  manufacturer?: string | null;
  item_number?: string | null;
  logo_url?: string | null;
  domain: string;
  categories: string[];
  custom_prompt: string;
  status: string;
  seeded: boolean;
  primary_source_id?: string | null;
  document_count: number;
  max_documents: number;
  sources: ProductSourceSummary[];
  processes: string[];
  voltages: string[];
  quick_actions: Array<{ label: string; message: string }>;
  ingestion: {
    status: string;
    stage: string;
    progress: number;
    message: string;
    error?: string | null;
  };
}

export interface ChatRequestPayload {
  conversation_id?: string;
  session_id?: string | null;
  product_id: string;
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

export async function fetchProducts(): Promise<{
  products: ProductSummary[];
  default_product_id: string;
}> {
  const res = await fetch(buildBackendUrl("/api/products"));
  if (!res.ok) {
    throw new Error(`Products API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchProduct(productId: string): Promise<ProductSummary> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}`));
  if (!res.ok) {
    throw new Error(`Product API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function deleteProduct(productId: string): Promise<void> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}`), { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Delete product failed: ${res.status} ${res.statusText}`);
  }
}

export async function updateProduct(productId: string, updates: { description?: string; categories?: string[]; custom_prompt?: string }): Promise<ProductSummary> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    throw new Error(`Update product failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function createProduct(name: string, description: string, categories: string[] = []): Promise<ProductSummary> {
  const res = await fetch(buildBackendUrl("/api/products"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description, categories }),
  });
  if (!res.ok) {
    throw new Error(`Create product failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function uploadProductDocuments(
  productId: string,
  files: File[],
  sourceType = "manual"
): Promise<ProductSummary> {
  const form = new FormData();
  form.append("source_type", sourceType);
  for (const file of files) form.append("files", file);
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/documents`), {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Upload failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function replaceProductDocument(
  productId: string,
  sourceId: string,
  file: File,
  sourceType = "manual"
): Promise<ProductSummary> {
  const form = new FormData();
  form.append("file", file);
  form.append("source_type", sourceType);
  const res = await fetch(
    buildBackendUrl(`/api/products/${productId}/documents/${sourceId}/replace`),
    {
      method: "POST",
      body: form,
    }
  );
  if (!res.ok) {
    throw new Error(`Replace failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function deleteProductDocument(
  productId: string,
  sourceId: string
): Promise<ProductSummary> {
  const res = await fetch(
    buildBackendUrl(`/api/products/${productId}/documents/${sourceId}`),
    { method: "DELETE" }
  );
  if (!res.ok) {
    throw new Error(`Delete failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function uploadProductLogo(
  productId: string,
  file: File
): Promise<ProductSummary> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/logo`), {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    throw new Error(`Logo upload failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function startProductIngestion(productId: string): Promise<{
  status: string;
  stage: string;
  progress: number;
  message: string;
}> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/ingest`), {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Start ingestion failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function getProductIngestionStatus(productId: string): Promise<{
  status: string;
  stage: string;
  progress: number;
  message: string;
  error?: string | null;
}> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/ingest/status`));
  if (!res.ok) {
    throw new Error(`Status API failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}


// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface DBMessage {
  id: number;
  role: "user" | "assistant";
  content: Record<string, unknown>;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  product_id: string;
  title: string;
  messages: DBMessage[];
}

export async function listConversations(productId: string): Promise<ConversationSummary[]> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/conversations`));
  if (!res.ok) return [];
  const data = await res.json();
  return data.conversations;
}

export async function createConversation(productId: string): Promise<{ id: string }> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/conversations`), { method: "POST" });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function getConversation(conversationId: string): Promise<ConversationDetail | null> {
  const res = await fetch(buildBackendUrl(`/api/conversations/${conversationId}`));
  if (!res.ok) return null;
  return res.json();
}

export async function updateConversationTitle(conversationId: string, title: string): Promise<void> {
  await fetch(buildBackendUrl(`/api/conversations/${conversationId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversationAPI(conversationId: string): Promise<void> {
  await fetch(buildBackendUrl(`/api/conversations/${conversationId}`), { method: "DELETE" });
}


// ---------------------------------------------------------------------------
// Memories (per-product preferences)
// ---------------------------------------------------------------------------

export interface Memory {
  id: number;
  content: string;
  source: string;
  created_at: string;
}

export async function listMemories(productId: string): Promise<{ memories: Memory[]; max: number }> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/memories`));
  if (!res.ok) return { memories: [], max: 5 };
  return res.json();
}

export async function addMemory(productId: string, content: string): Promise<Memory | null> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/memories`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) return null;
  return res.json();
}

export async function deleteMemory(memoryId: number): Promise<void> {
  await fetch(buildBackendUrl(`/api/memories/${memoryId}`), { method: "DELETE" });
}
