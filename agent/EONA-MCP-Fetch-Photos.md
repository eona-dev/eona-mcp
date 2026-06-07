# EONA MCP Fetch Photos

This guide is for Agents using EONA MCP to show or send photos to the user.

## Core Rule

Use the EONA fetch tool with `photo_ids`.

Do not use:

- source file paths
- `/photos/...` paths
- raw filesystem listing
- raw SQLite inspection

EONA MCP source paths may be container-local or runtime-local. They are not a
client retrieval contract.

## Workflow

1. Use the EONA query tool to find a small candidate set.
2. Select `photo.id` values from the query result.
3. Call the EONA fetch tool with `photo_ids`.
4. For HTTP MCP, show the returned asset URLs as links.
5. For stdio MCP, show the returned image content.

Default to a small sample:

- 1 photo for a direct request
- 2-4 photos for a visual sample

Do not fetch an unbounded result set.

## Fetch Tool Shape

```json
{
  "photo_ids": ["pho_..."],
  "max_bytes": 12582912
}
```

`max_bytes` is optional. Increase it only when the first fetch reports that a
selected photo exceeds the current byte limit.

## HTTP MCP Output

For HTTP MCP, fetch returns temporary asset URLs, such as:

```text
http://localhost:8711/assets/<opaque-name>.jpg
```

Use URLs as links. Do not promise that MCP inline image blocks or Markdown image
embedding will display in the chat UI. The URL is minted by an authenticated MCP
fetch call and does not expose the source file path.

## Stdio MCP Output

For stdio MCP, fetch returns bounded image content directly through MCP.

## Failure Handling

If fetch fails:

- explain which `photo_id` failed
- continue with successful fetched photos when possible
- do not fall back to file paths
- query again for replacement `photo.id` values if needed
