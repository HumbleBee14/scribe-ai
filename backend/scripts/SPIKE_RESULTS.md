# Claude Agent SDK Spike Results

## Conclusion: Migration is feasible and should be done

The `claude-agent-sdk` (pip: `claude-agent-sdk`, import: `claude_agent_sdk`) works with our architecture. Custom tools via MCP work correctly. Streaming events map to our SSE contract.

## Key Findings

### 1. Custom tools work via MCP
- Use `@tool` decorator + `create_sdk_mcp_server()`
- Tool names get prefixed: `lookup_duty_cycle` becomes `mcp__welding__lookup_duty_cycle`
- Return format MUST be MCP CallToolResult: `{"content": [{"type": "text", "text": json.dumps(data)}]}`

### 2. Streaming events available
With `include_partial_messages=True`, the SDK yields `StreamEvent` objects containing:
- `content_block_start` with `tool_use` type (maps to our `tool_start`)
- `content_block_delta` with `text_delta` (maps to our `text_delta`)
- `content_block_start` with `thinking` type (maps to our `thinking`)
- `message_delta` with `stop_reason` (maps to our `done`)
- Plus `AssistantMessage` and `ResultMessage` for complete turns

### 3. Session management built-in
- `session_id` option for conversation persistence
- `resume` option for continuing sessions
- `fork_session` for branching

### 4. What changes in our code
- `provider.py`: replace `AnthropicProvider` with `AgentSDKProvider` using `query()`
- `orchestrator.py`: simplify, the SDK handles the tool loop
- `tools.py`: wrap each tool handler with `@tool` decorator, return MCP format
- `chat.py`: map SDK events to our SSE events

### 5. What stays the same
- Frontend SSE contract (no changes needed)
- Evidence model, structured store, validation
- Tool logic (lookup functions stay the same, just wrapped differently)
- Session sidebar, message rendering, artifacts

## Cost
Spike test: $0.05 per query (includes ToolSearch overhead for MCP tool discovery).
