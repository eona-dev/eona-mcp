# eona-mcp

AGPL MCP product extracted from EONA. It exposes the EONA MCP surface and calls a pinned private `eona-cli` install by explicit path.

Tools:

- `eona.<project>.append`
- `eona.<project>.list`
- `eona.<project>.reset`
- `eona.<project>.refresh`
- `eona.<project>.query`

The default CLI install root is `~/.eona/eona-mcp`; workspace/session data remains under `~/.eona/eona-mcp/workspace`.
