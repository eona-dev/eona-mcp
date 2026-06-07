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
4. Show the returned asset URLs as links.

Default to a small sample:

- 1 photo for a direct request
- 2-4 photos for a visual sample

Do not fetch an unbounded result set.

## Fetch Tool Shape

```json
{
  "photo_ids": ["pho_..."],
  "max_bytes": 12582912,
  "include_content": false
}
```

`max_bytes` is optional. Increase it only when the first fetch reports that a
selected photo exceeds the current byte limit.

`include_content` is optional. Keep it `false` by default. Set it to `true` only
when the MCP client is known to render MCP image content blocks reliably.

## Output

Fetch returns temporary opaque asset URLs. Image assets are bounded to 2400px on
their longest side. Docker HTTP MCP returns `http://` asset URLs, such as:

```text
http://localhost:8711/assets/<opaque-name>.jpg
```

Stdio MCP returns `file://` asset URLs, such as:

```text
file:///Users/example/.eona/workspace/assets/<opaque-name>.jpg
```

Use URLs as links. Do not promise that MCP inline image blocks or Markdown image
embedding will display in the chat UI. The URL is minted by an authenticated MCP
fetch call and does not expose the source file path.

When `include_content` is `true`, fetch also returns 1200px-bounded MCP `image`
preview content blocks for clients that support them. Treat those blocks as an
optional display path; the asset URL remains the stable retrieval contract for
the fetched asset.

## Failure Handling

If fetch fails:

- explain which `photo_id` failed
- continue with successful fetched photos when possible
- do not fall back to file paths
- query again for replacement `photo.id` values if needed
