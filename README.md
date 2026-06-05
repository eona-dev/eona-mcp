# eona-mcp

AGPL MCP product extracted from EONA. It exposes the EONA MCP surface and calls a pinned private `eona-cli` install by explicit path.

Tools:

- `eona.<project>.append`
- `eona.<project>.list`
- `eona.<project>.reset`
- `eona.<project>.refresh`
- `eona.<project>.query`

EONA installs as a product family under `~/.eona` by default:

- `~/.eona/eona-mcp`: MCP surface and launchers
- `~/.eona/eona-cli`: sealed CLI runtime
- `~/.eona/workspace`: shared local workspace/session data

Set `EONA_FAMILY_ROOT`, `EONA_MCP_INSTALL_ROOT`, `EONA_CLI_INSTALL_ROOT`, `EONA_CLI`, or `EONA_MCP_WORKSPACE` to override these defaults.
