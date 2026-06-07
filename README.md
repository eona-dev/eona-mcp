# EONA MCP

```text
Expose local EONA photo metadata to Codex, Claude, and other MCP clients.
```

EONA MCP is a project-scoped MCP server built on top of EONA CLI.

Each project provides its own photo workspace, metadata index, and MCP tool namespace.

---

## Quick Start

Recommended: attach photo folders during bootstrap, before adding EONA MCP to
your MCP client. Indexing can take time, and bootstrap can show progress in a
normal terminal.

Hosted bootstrap:

```bash
export EONA_SOURCES_JSON='["/path/to/photos"]'
curl -sSL https://mcp.eona.dev/bootstrap.sh | sh
```

Repository checkout:

```bash
git clone https://github.com/isemptyc/eona-mcp.git
cd eona-mcp
export EONA_SOURCES_JSON='["/path/to/photos"]'
bash bootstrap/bootstrap.sh
```

When bootstrap succeeds, configure your MCP client to use:

```text
~/.eona/eona-mcp/eona-mcp-stdio.sh
```

---

## Existing Projects

Bootstrap does not modify existing project sources by default.

To intentionally append or refresh sources:

```bash
export EONA_FORCE_APPEND=1
```

---

## Docker HTTP MCP

Use Docker when you want HTTP MCP containers instead of the local stdio launcher.
The Docker image runs EONA MCP and EONA CLI in an isolated, prebuilt, and a preserved
running environment for the lifetime of the container.

Start from the same checkout:

```bash
git clone https://github.com/isemptyc/eona-mcp.git
cd eona-mcp
```

Prepare local environment settings:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```text
EONA_PROJECT_A_PHOTOS=/path/to/photos
EONA_PROJECT_A_BEARER_TOKEN=change-me-project-a
```

Start the default project:

```bash
docker compose up
```

To run the optional second project, set the `EONA_PROJECT_B_*` values in `.env`
and start with:

```bash
docker compose --profile project-b up
```

The default HTTP endpoint is:

```text
http://localhost:8711/mcp
```

Configure your MCP client with the bearer token from `.env`:

```text
Authorization: Bearer change-me-project-a
```

For the optional second project, use the `EONA_PROJECT_B_BEARER_TOKEN` value
instead:

```text
Authorization: Bearer change-me-project-b
```

Docker MCP containers are standalone and ephemeral. They do not share a
workspace volume; each container stores its index under its own `/workspace`.
Removing a container removes its indexed data. Photo folders are mounted
read-only at `/photos`.

---

## MCP Tools

exposes:

```text
eona-mcp.<project>.append
eona-mcp.<project>.list
eona-mcp.<project>.refresh
eona-mcp.<project>.reset
eona-mcp.<project>.query
eona-mcp.<project>.fetch
```

The query tool returns metadata and `photo.id` values. The fetch tool retrieves
indexed photos by `photo.id`; clients should not pass file paths. HTTP MCP
returns `http://` asset URLs; stdio MCP returns `file://` asset URLs. Fetch can
also return MCP image content blocks when called with `include_content=true`,
but asset URLs remain the stable cross-client retrieval contract.

---

## EONA CLI

`eona-cli` is the local EONA runtime used by `eona-mcp` to index photo folders, maintain project sessions, and execute EONA Query v1 plans.

Repository:

```text
https://github.com/isemptyc/eona-cli
```

`eona-cli` is distributed separately under GPL-3.0. `eona-mcp` does not bundle
`eona-cli`; it integrates with it as an external runtime dependency.

## License

`eona-mcp` is licensed under the MIT License. See `LICENSE`.
