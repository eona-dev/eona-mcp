# eona-mcp

AGPL MCP product extracted from EONA. It exposes the EONA MCP surface and calls the sibling sealed `eona-cli` runtime by explicit path.

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

`contracts/eona-cli-dependency.json` describes the runtime compatibility surface that MCP expects from `eona-cli`. Bootstrap artifact pins live separately in `contracts/eona-cli-bootstrap.json`, because `eona-cli` may upgrade itself after installation.
