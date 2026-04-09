# Claude Agent SDK Spike Results

## Status: Migration complete

The `claude-agent-sdk` package is now the orchestration foundation. The spike is done. This file documents what was learned.

## Key Findings

### 1. Custom tools work via MCP
- Use `@tool` decorator + `create_sdk_mcp_server()`
- Tool names get prefixed: `lookup_duty_cycle` becomes `mcp__welding-knowledge__lookup_duty_cycle`
- Return format MUST be MCP CallToolResult: `{"content": [{"type": "text", "text": json.dumps(data)}]}`

### 2. Streaming events available
With `include_partial_messages=True`, the SDK yields `StreamEvent` objects containing:
- `content_block_start` with `tool_use` type (maps to our `tool_start`)
- `content_block_delta` with `text_delta` (maps to our `text_delta`)
- `message_delta` with `stop_reason` (maps to our `done`)
- Plus `AssistantMessage` and `ResultMessage` for complete turns

### 3. Multi-turn sessions
- SDK persists sessions to disk automatically
- Capture `session_id` from `ResultMessage`, pass `resume=session_id` on next turn
- No need to manage message arrays ourselves

### 4. Architecture after migration
- `orchestrator.py`: uses `query()` + `resume` for multi-turn
- `tools_mcp.py`: MCP tool wrappers around existing tool execution logic
- `tools.py`: unchanged execution logic (structured store lookups, validation, caching)
- `chat.py`: maps SDK events to frontend SSE events
- Built-in `Read` tool enabled for broad manual questions alongside custom MCP tools

### 5. Known SSE contract gaps
- `tool_start.data.input` is `{}` (tool args not available at `content_block_start` time, they stream via deltas)
- `tool_end.data.ok` is always `true` (SDK handles errors internally)
- These are acceptable for the current frontend but should be tightened if the UI needs them

### 6. Full-context mode change
The original "explicit full-context injection" (Phase 5) is replaced by enabling the SDK's built-in `Read` tool pointing at the manual PDF. This is simpler and lets the SDK handle PDF reading natively. Exact-data tools still handle all high-risk factual lookups.

## Cost
Approximately $0.06 to $0.12 per query (includes ToolSearch overhead for MCP tool discovery).
