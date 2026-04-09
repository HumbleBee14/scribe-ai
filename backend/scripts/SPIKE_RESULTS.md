# Claude Agent SDK Spike Results

## Status: Optional path only

The `claude-agent-sdk` package was evaluated successfully, but it is not the default local runtime. This file documents what was learned and why the app now defaults to the raw Anthropic tool loop.

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
- That extra dependency is not safe to assume for evaluator machines
- `orchestrator.py` therefore uses the raw Anthropic tool loop by default
- The Agent SDK path remains available as an optional code path when the local Claude CLI exists

### 5. Known SSE contract gaps
- `tool_start.data.input` is `{}` (tool args not available at `content_block_start` time, they stream via deltas)
- `tool_end.data.ok` is always `true` (SDK handles errors internally)
- These are acceptable for the current frontend but should be tightened if the UI needs them

### 6. Full-context mode in the shipping app
The shipping app uses explicit full-context PDF injection via the Anthropic Messages API. The SDK `Read` path remains useful for experimentation, but the zero-setup local runtime does not depend on it.

## Cost
Approximately $0.06 to $0.12 per query (includes ToolSearch overhead for MCP tool discovery).
