# EONA MCP

```text
Expose local EONA photo metadata to Codex, Claude, and other MCP clients.
```

EONA MCP is a project-scoped MCP server built on top of EONA CLI.

Each project provides its own photo workspace, metadata index, and MCP tool namespace.

---

## Install

```bash
curl -sSL https://mcp.eona.dev/bootstrap.sh | sh
```

When bootstrap succeeds, configure your MCP client to use:

```text
~/.eona/eona-mcp/eona-mcp-stdio.sh
```

---

## Quick Start

Recommended: attach photo folders during bootstrap, before adding EONA MCP to
your MCP client. Indexing can take time, and bootstrap can show progress in a
normal terminal.

```bash
export EONA_SOURCES_JSON='["/path/to/photos"]'

curl -sSL https://mcp.eona.dev/bootstrap.sh | sh
```

The default project is:

```text
my-photos
```

---

## Existing Projects

Bootstrap does not modify existing project sources by default.

To intentionally append or refresh sources:

```bash
export EONA_SOURCES_JSON='["/path/to/photos"]'
export EONA_FORCE_APPEND=1

curl -sSL https://mcp.eona.dev/bootstrap.sh | sh
```

---

## Docker HTTP MCP

Use Docker when you want HTTP MCP containers instead of the local stdio launcher.
The Docker image runs EONA MCP and EONA CLI in an isolated, prebuilt
environment: no random runtime downloads, no auto-upgrades, and a preserved
running environment for the lifetime of the container.

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

The default HTTP endpoint is:

```text
http://localhost:8711/mcp
```

To run the optional second project, set the `EONA_PROJECT_B_*` values in `.env`
and start with:

```bash
docker compose --profile project-b up
```

Docker MCP containers are standalone and ephemeral. They do not share a
workspace volume; each container stores its index under its own `/workspace`.
Removing a container removes its indexed data. Photo folders are mounted
read-only at `/photos`.

HTTP MCP startup prepares location data before listening by default. After
indexing, EONA MCP asks EONA CLI for the indexed countries, then warms
`location.admin_path` per country so agent queries do not trigger long Cadis
preparation work. Set `EONA_MCP_HTTP_PREPARE_LOCATION=0` to skip this warm-up.

HTTP fetch publishes requested photos as temporary assets under `/workspace/assets`
and returns URLs such as `http://localhost:8711/assets/<opaque-name>.jpg`.
The MCP endpoint still requires the bearer token; asset URLs are minted only by
authenticated fetch calls and do not expose source file paths.

---

## MCP Tools

A project named:

```text
my-photos
```

exposes:

```text
eona.my-photos.append
eona.my-photos.list
eona.my-photos.refresh
eona.my-photos.reset
eona.my-photos.query
eona.my-photos.fetch
```

The query tool executes an EONA Query v1 plan against the project's metadata index.
The fetch tool retrieves indexed photos by `photo.id`; clients should not pass
file paths. HTTP MCP returns temporary asset URLs for fetched photos; stdio MCP
returns image content directly.

Agents should read:

```text
eona://agent/how-to-query
eona://agent/how-to-fetch-photos
```

before issuing queries or fetching photos. These resources are backed by:

```text
agent/EONA-MCP-Query-v1.md
agent/EONA-MCP-Fetch-Photos.md
```

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
