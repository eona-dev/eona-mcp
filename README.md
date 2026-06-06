# eona-mcp

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
