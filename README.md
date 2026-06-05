# eona-mcp

AGPL MCP product extracted from EONA. It exposes the EONA MCP surface and calls the sibling sealed `eona-cli` runtime by explicit path.

Tools:

- `eona.<project>.append`
- `eona.<project>.list`
- `eona.<project>.reset`
- `eona.<project>.refresh`
- `eona.<project>.query`

Install from a checkout or release bundle:

```bash
./bootstrap/bootstrap.sh
```

EONA installs as a product family under `~/.eona` by default:

- `~/.eona/eona-mcp`: MCP surface and launchers
- `~/.eona/eona-cli`: sealed CLI runtime
- `~/.eona/workspace`: shared local workspace/session data

The MCP bootstrap installs the MCP surface and provisions `eona-cli` as a sibling runtime when `~/.eona/eona-cli/bin/eona` is missing or older than `contracts/eona-cli-dependency.json` requires. It leaves compatible or newer CLI runtimes in place so `eona-cli` can self-upgrade independently; use `--repair-cli` to run the CLI bootstrap anyway. Repair refuses to replace a newer local CLI with the bootstrap target unless `--allow-cli-downgrade` is set.

Set `EONA_FAMILY_ROOT`, `EONA_MCP_INSTALL_ROOT`, `EONA_CLI_INSTALL_ROOT`, `EONA_CLI`, or `EONA_MCP_WORKSPACE` to override runtime defaults. Bootstrap also supports `--family-root`, `--install-dir`, `--cli-install-dir`, and `--workspace-dir`.

`contracts/eona-cli-dependency.json` describes the runtime compatibility surface that MCP expects from `eona-cli`. Bootstrap artifact pins live separately in `contracts/eona-cli-bootstrap.json`, because `eona-cli` may upgrade itself after installation.
