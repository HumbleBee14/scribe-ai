# Chat Persistence & Shareable URLs

## Problem

Conversations are stored in browser localStorage only. This means:
- Chats don't persist across browsers/devices
- No shareable URLs (all chats share one URL)
- Data lost on browser clear
- Right sidebar state (artifacts, sources) tied to ephemeral client state

## Solution

Persist conversations and messages in SQLite. Each conversation gets a unique
URL. Anyone with the URL can view and continue the conversation.

## Database Schema

### conversations table

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,              -- nanoid (short, URL-safe)
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',    -- auto-set from first user message (first 80 chars)
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_product
    ON conversations(product_id, updated_at DESC);
```

### messages table

```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,               -- 'user' | 'assistant'
    content TEXT NOT NULL,            -- JSON blob (see Message Content below)
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id);
```

## Message Content (JSON blob)

### User message

```json
{
  "text": "What polarity for TIG welding?",
  "images": ["/uploads/img_abc123.jpg"]
}
```

- `text`: The user's question
- `images`: Array of file paths (stored on disk, NOT base64).
  If user uploads an image, backend saves to
  `data/products/{product_id}/uploads/{filename}` and stores the path.

### Assistant message

```json
{
  "text": "For TIG welding on the OmniPro 220, you need DCEN polarity...",
  "toolCalls": [
    {"name": "lookup_polarity", "input": {"process": "tig"}, "result": "..."}
  ],
  "sourcePages": [
    {"sourceId": "owner-manual", "page": 12, "label": "Page 12"}
  ],
  "artifacts": [
    {"id": "art_1", "type": "svg", "title": "TIG Polarity Diagram", "content": "<svg>...</svg>"}
  ],
  "followUps": [
    "What tungsten size for TIG?",
    "Show me the TIG torch setup"
  ]
}
```

This preserves everything the right sidebar needs:
- `sourcePages` -> Source Viewer panel
- `artifacts` -> Artifacts panel
- `toolCalls` -> Tool call indicators in message bubbles
- `followUps` -> Quick reply buttons

## URL Structure

```
/products/{productId}/chat/{conversationId}
```

Examples:
- `/products/vulcan-omnipro-220/chat/k7x9m2` (existing conversation)
- `/products/vulcan-omnipro-220` (workspace landing, no conversation selected)

## API Endpoints

### List conversations
```
GET /api/products/{product_id}/conversations
Response: { conversations: [{ id, title, message_count, updated_at }] }
```

### Create conversation
```
POST /api/products/{product_id}/conversations
Response: { id, product_id, title, created_at }
```

### Get conversation with messages
```
GET /api/conversations/{conversation_id}
Response: { id, product_id, title, messages: [...] }
```

### Delete conversation
```
DELETE /api/conversations/{conversation_id}
Response: { deleted: true }
```

### Save messages (called by chat stream handler)
Internal -- not a public endpoint. The existing `/api/chat/stream` handler
saves messages to DB after streaming completes.

## User Image Uploads

1. Frontend sends base64 image in chat request (existing flow)
2. Backend saves file to `data/products/{product_id}/uploads/{uuid}.{ext}`
3. Message JSON stores the path reference, not the base64 data
4. When loading conversation, frontend requests image via existing asset endpoint

New endpoint for serving uploads:
```
GET /api/products/{product_id}/assets/uploads/{filename}
```

## Frontend Changes

### New route
```
/products/[productId]/chat/[conversationId]/page.tsx
```

### Workspace landing (`/products/[productId]`)
- Shows conversation list + welcome screen
- "New" button creates conversation via API, navigates to `/chat/{id}`

### Chat page (`/products/[productId]/chat/[conversationId]`)
- Loads conversation + messages from API on mount
- Messages rendered exactly as today (same components)
- Right sidebar populated from message data (artifacts, sources)
- New messages saved to DB via the stream handler

### History sidebar
- Fetches from `/api/products/{id}/conversations` instead of localStorage
- Links navigate to `/chat/{conversationId}` URLs

### Remove localStorage persistence
- Delete `history.ts` localStorage functions
- Remove `persistMessages` / `loadMessages` from `useChat`

## Claude SDK Session (per-product, not per-conversation)

All conversations within a product share the same system prompt, page
summaries, tools, and document context. Only the conversation history differs.

- Store `sdk_session_id` on the **product** level (not per conversation)
- All chats for a product reuse the same SDK session for prompt caching
- The expensive context (system prompt + document summaries) stays cached as
  long as ANY user is chatting with that product within the 5-min TTL
- Individual conversation history is injected per-request from our DB
- If SDK session expires or fails to resume, a new one is created transparently

Schema change: `sdk_session_id` moves from `conversations` table to `products`
table (add column via migration).

## What stays the same

- Chat streaming (SSE) -- unchanged
- Message rendering components -- unchanged
- Artifact rendering -- unchanged
- Source viewer -- unchanged
- Agent orchestrator -- unchanged (just receives session ID)
- Tool system -- unchanged

## Migration

- On first load after deployment, localStorage conversations are gone
  (acceptable -- this is a fresh start with proper persistence)
- No migration from localStorage to DB needed
