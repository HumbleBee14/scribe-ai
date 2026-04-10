# Claude Agent SDK Spike Results

## Status: Shipping runtime

The `claude-agent-sdk` package was evaluated successfully and is now the only runtime used by the app. This file documents what was learned while validating the SDK transport, MCP tools, and streaming event model.

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

### 4. Practical runtime decision
- `claude-agent-sdk` depends on the local Claude CLI transport
- On Windows dev setups, the main trap was subprocess/event-loop configuration rather than the SDK design itself
- The shipping backend now uses the Agent SDK directly and surfaces runtime errors instead of maintaining a second orchestration stack

### 5. Known SSE contract gaps
- `tool_start.data.input` is `{}` (tool args not available at `content_block_start` time, they stream via deltas)
- `tool_end.data.ok` is emitted from our mapper, not from native SDK result semantics
- These are acceptable for the current frontend but should be tightened further if the UI starts depending on exact tool error metadata

### 6. Full-context mode in the shipping app
The shipping app relies on the SDK's built-in `Read` tool for broad manual access. Exact-data MCP tools still handle high-risk factual lookups, and `Read` covers open-ended document questions without a second PDF-injection path.

## Cost
Approximately $0.06 to $0.12 per query (includes ToolSearch overhead for MCP tool discovery).
