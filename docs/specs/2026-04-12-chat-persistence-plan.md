# Chat Persistence & Shareable URLs - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist conversations in SQLite with shareable URLs per chat session.

**Architecture:** Two new DB tables (conversations, messages). Backend saves messages during stream. Frontend loads from API, routes to `/products/{id}/chat/{convId}`. localStorage removed.

**Tech Stack:** SQLite, FastAPI, Next.js dynamic routes, nanoid for IDs.

---

### Task 1: Backend DB schema + CRUD functions

**Files:**
- Modify: `backend/app/core/database.py`

- [ ] **Step 1: Add conversations and messages tables to init_db()**

Add after the existing `toc_entries` table creation:

```python
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_product
    ON conversations(product_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);
```

- [ ] **Step 2: Add CRUD functions**

```python
import json
import secrets
import string

def _nanoid(size: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(size))

def create_conversation(product_id: str, title: str = "") -> dict[str, Any]:
    conn = _get_conn()
    conv_id = _nanoid()
    now = _now()
    conn.execute(
        "INSERT INTO conversations (id, product_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, product_id, title, now, now),
    )
    conn.commit()
    return {"id": conv_id, "product_id": product_id, "title": title, "created_at": now, "updated_at": now}

def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if row is None:
        return None
    conv = dict(row)
    msgs = conn.execute(
        "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    conv["messages"] = [
        {"id": m["id"], "role": m["role"], "content": json.loads(m["content"]), "created_at": m["created_at"]}
        for m in msgs
    ]
    return conv

def list_conversations(product_id: str) -> list[dict[str, Any]]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT c.id, c.title, c.created_at, c.updated_at,
                  (SELECT COUNT(*) FROM messages WHERE conversation_id = c.id) as message_count
           FROM conversations c WHERE c.product_id = ?
           ORDER BY c.updated_at DESC""",
        (product_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def add_message(conversation_id: str, role: str, content: dict) -> dict[str, Any]:
    conn = _get_conn()
    now = _now()
    cursor = conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, json.dumps(content), now),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (now, conversation_id),
    )
    conn.commit()
    return {"id": cursor.lastrowid, "role": role, "content": content, "created_at": now}

def update_conversation_title(conversation_id: str, title: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?", (title, _now(), conversation_id))
    conn.commit()

def delete_conversation(conversation_id: str) -> bool:
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    return cursor.rowcount > 0
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/database.py
git commit -m "Add conversations and messages tables with CRUD functions"
```

---

### Task 2: Backend conversation API endpoints

**Files:**
- Create: `backend/app/api/conversations.py`
- Modify: `backend/app/core/bootstrap.py` (register router)

- [ ] **Step 1: Create conversations router**

```python
"""Conversation CRUD API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import database as db

router = APIRouter(tags=["conversations"])


class UpdateConversationRequest(BaseModel):
    title: str


@router.get("/api/products/{product_id}/conversations")
def list_conversations_api(product_id: str) -> dict:
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")
    return {"conversations": db.list_conversations(product_id)}


@router.post("/api/products/{product_id}/conversations")
def create_conversation_api(product_id: str) -> dict:
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Unknown product: {product_id}")
    return db.create_conversation(product_id)


@router.get("/api/conversations/{conversation_id}")
def get_conversation_api(conversation_id: str) -> dict:
    conv = db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.patch("/api/conversations/{conversation_id}")
def update_conversation_api(conversation_id: str, req: UpdateConversationRequest) -> dict:
    conv = db.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.update_conversation_title(conversation_id, req.title.strip())
    return db.get_conversation(conversation_id)


@router.delete("/api/conversations/{conversation_id}")
def delete_conversation_api(conversation_id: str) -> dict:
    if not db.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True}
```

- [ ] **Step 2: Register router in bootstrap.py**

Add import and `app.include_router(conversations_router)`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/conversations.py backend/app/core/bootstrap.py
git commit -m "Add conversation CRUD API endpoints"
```

---

### Task 3: Backend - save messages during chat stream

**Files:**
- Modify: `backend/app/api/chat.py`

- [ ] **Step 1: Modify _event_stream to save messages to DB**

Key changes to `_event_stream()`:
1. Accept `conversation_id` parameter
2. If no conversation_id, create one
3. Save user message to DB before streaming
4. Accumulate assistant response during streaming
5. Save assistant message to DB on "done" event
6. Auto-set conversation title from first user message

- [ ] **Step 2: Modify ChatRequest to include conversation_id**

```python
class ChatRequest(BaseModel):
    conversation_id: str | None = None
    product_id: str | None = None
    message: str
    images: list[ImageInput] | None = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/chat.py
git commit -m "Save chat messages to DB during stream"
```

---

### Task 4: Backend - user image upload to disk

**Files:**
- Modify: `backend/app/api/chat.py`
- Modify: `backend/app/api/products.py` (add upload asset route)

- [ ] **Step 1: Save user images to disk in chat handler**

When images are present in the request:
1. Decode base64
2. Save to `data/products/{product_id}/uploads/{uuid}.{ext}`
3. Store path reference in message content JSON

- [ ] **Step 2: Add upload asset serving endpoint**

```python
@router.get("/{product_id}/assets/uploads/{filename}")
def get_upload_asset(product_id: str, filename: str) -> FileResponse:
    safe_name = Path(filename).name
    path = PRODUCTS_DIR / product_id / "uploads" / safe_name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Upload not found")
    return FileResponse(path)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/chat.py backend/app/api/products.py
git commit -m "Save user images to disk, serve via asset endpoint"
```

---

### Task 5: Frontend - conversation API functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add conversation types and API functions**

```typescript
export interface ConversationSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail {
  id: string;
  product_id: string;
  title: string;
  messages: Array<{
    id: number;
    role: "user" | "assistant";
    content: Record<string, unknown>;
    created_at: string;
  }>;
}

export async function listConversations(productId: string): Promise<ConversationSummary[]> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/conversations`));
  if (!res.ok) throw new Error("Failed to list conversations");
  const data = await res.json();
  return data.conversations;
}

export async function createConversation(productId: string): Promise<{ id: string }> {
  const res = await fetch(buildBackendUrl(`/api/products/${productId}/conversations`), { method: "POST" });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const res = await fetch(buildBackendUrl(`/api/conversations/${conversationId}`));
  if (!res.ok) throw new Error("Conversation not found");
  return res.json();
}

export async function updateConversationTitle(conversationId: string, title: string): Promise<void> {
  await fetch(buildBackendUrl(`/api/conversations/${conversationId}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await fetch(buildBackendUrl(`/api/conversations/${conversationId}`), { method: "DELETE" });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "Add conversation API functions to frontend"
```

---

### Task 6: Frontend - new chat route

**Files:**
- Create: `frontend/src/app/products/[productId]/chat/[conversationId]/page.tsx`
- Modify: `frontend/src/app/products/[productId]/page.tsx`

- [ ] **Step 1: Create chat page route**

```typescript
import { ProductWorkspace } from "@/components/products/product-workspace";

interface Props {
  params: Promise<{ productId: string; conversationId: string }>;
}

export default async function ChatPage({ params }: Props) {
  const { productId, conversationId } = await params;
  return <ProductWorkspace initialProductId={productId} initialConversationId={conversationId} />;
}
```

- [ ] **Step 2: Update product landing page**

Pass no conversationId (workspace landing/new chat mode):

```typescript
export default async function ProductWorkspacePage({ params }: Props) {
  const { productId } = await params;
  return <ProductWorkspace initialProductId={productId} />;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/products/
git commit -m "Add /products/[id]/chat/[convId] route"
```

---

### Task 7: Frontend - update useChat hook for DB persistence

**Files:**
- Modify: `frontend/src/lib/use-chat.ts`

- [ ] **Step 1: Replace localStorage with API-backed persistence**

Key changes:
1. Remove `loadMessages()` and `persistMessages()` localStorage functions
2. On mount: if `conversationId` provided, fetch messages from API via `getConversation()`
3. Convert DB messages to `ChatMessage[]` format for rendering
4. Remove localStorage save on message change
5. Messages are saved by the backend during streaming (no frontend save needed)
6. After first user message: if no conversationId, create conversation via API, return new ID

- [ ] **Step 2: Add `conversationId` to the hook return**

The hook should return the current conversationId so the workspace can update the URL.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/use-chat.ts
git commit -m "Replace localStorage with DB-backed chat persistence"
```

---

### Task 8: Frontend - update ProductWorkspace for URL-based routing

**Files:**
- Modify: `frontend/src/components/products/product-workspace.tsx`

- [ ] **Step 1: Accept optional initialConversationId prop**

```typescript
interface Props {
  initialProductId: string;
  initialConversationId?: string;
}
```

- [ ] **Step 2: Update URL on conversation change**

When a new conversation is created or user selects from history, use `window.history.pushState()` to update URL to `/products/{id}/chat/{convId}` without full page reload.

- [ ] **Step 3: Handle "New" button**

"New" navigates to `/products/{id}` (no conversation) which shows the welcome screen.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/products/product-workspace.tsx
git commit -m "Update workspace for URL-based conversation routing"
```

---

### Task 9: Frontend - update history sidebar

**Files:**
- Modify: `frontend/src/components/layout/history-sidebar.tsx`

- [ ] **Step 1: Fetch conversations from API instead of localStorage**

Replace `listConversations()` from `history.ts` with API call.
Replace `deleteConversation()` with API call.
Replace `saveConversation()` (rename) with `updateConversationTitle()` API call.
Remove the 3-second polling interval -- fetch on mount and on conversation changes.

- [ ] **Step 2: Update navigation links**

Clicking a conversation should navigate to `/products/{productId}/chat/{conversationId}`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/history-sidebar.tsx
git commit -m "Update history sidebar to use API instead of localStorage"
```

---

### Task 10: Cleanup - remove localStorage persistence

**Files:**
- Delete: `frontend/src/lib/history.ts`
- Modify: any remaining imports of `history.ts`

- [ ] **Step 1: Remove history.ts**

Delete the file entirely.

- [ ] **Step 2: Remove any remaining imports**

Search for `from "@/lib/history"` and remove.

- [ ] **Step 3: Verify build**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Remove localStorage chat persistence, fully DB-backed now"
```

---

### Task 11: Commit .db and verify

- [ ] **Step 1: Add updated local.db to git**

The schema has new tables. Commit the updated DB.

- [ ] **Step 2: Full integration test**

1. Start backend + frontend
2. Open workspace -- should show empty conversation list
3. Send a message -- conversation created, URL updates
4. Refresh page -- conversation loads from DB
5. Share URL -- opens same conversation
6. Click "New" -- new conversation
7. Check sidebar -- shows all conversations
8. Delete conversation -- removed from list

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "Chat persistence complete: DB-backed conversations with shareable URLs"
```
