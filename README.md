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

Attach photo folders during bootstrap:

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
```

The query tool executes an EONA Query v1 plan against the project's metadata index.

Agents should read:

```text
eona://agent/how-to-query
```

before issuing queries.

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
