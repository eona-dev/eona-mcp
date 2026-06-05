# EONA Query v1

This guide is for Agents using **Eona Query v1**

## Core Rule

You own:
- user-intent interpretation
- query planning
- result interpretation
- user-facing explanation

That means:

- the user should ask the question in natural language
- you should convert that into Eona Query v1 JSON
- you should run the query and explain the result
- you should not offload the planning step back to the user
- you should answer like a helpful operator, not like a protocol designer

Eona owns:
- query protocol
- query semantics
- SQL execution
- on-demand source preparation
- on-demand semantic preparation

Do not write SQL. Stay inside the supported Eona Query v1 vocabulary.

## Eona Query v1

Always send a single JSON object with:

- `query_version`
- `anchor`
- `select`
- optional `filters`
- optional `group_by`
- optional `sort_by`
- optional `limit`

Always use:

```json
"query_version": 1
```

Filters and sorts use typed entity plans such as `{"entity":"time","attribute":"year","operator":"==","value":2026}` and `{"entity":"time","attribute":"taken_at","order":"asc"}`.

## Limit And Artifact Guidance

Use `limit` deliberately.

- omit `limit` or use a small integer for previews, samples, and top-N answers
- use `limit: null` only when the Agent needs the exhaustive row set
- expect results above 50 rows, or very large row payloads, to be returned through `result.artifact` instead of inline `result.rows`

When `result.artifact` is present, read the JSON file at `result.artifact.path`. It contains the query rows. Use `result.row_count` as the canonical total row count.

Do not treat artifact output as an issue. It is the normal large-result transport for exhaustive local queries.

## Default Duplicate Suppression

Normal photo queries hide rows marked as duplicate by EONA's metadata-level duplicate semantics.

Agents do not need to add an explicit duplicate filter for ordinary questions. If duplicate semantic status is failed or stale, report that as a query-quality follow-up rather than changing the user's query intent.

## Supported Entities

### `photo`

- `id`
- `content_id`

### `time`

- `taken_at`
- `year`
- `month`
- `day`
- `hour`
- `minute`
- `second`

### `camera`

- `make`
- `model`

### `camera_detail`

- `lens`
- `focal_length_mm`
- `aperture`
- `iso`
- `shutter_speed`

Camera detail is deferred semantic metadata. A newly introduced source folder may not have these fields prepared yet.

Use `camera.*` for baseline device make/model questions. Use `camera_detail.*` only when the user asks for lens, focal length, aperture, ISO, shutter speed, or similar camera-detail attributes.

When a query uses `camera_detail.*`, EONA may run scoped camera-detail extraction before returning the final result.

### `location`

- `country`
- `admin_label`
- `admin_path`

Location exposes privacy-preserving place labels:

- Cadis-derived place labels from deterministic semantic resolution

Do not request raw GPS latitude, longitude, or altitude. EONA does not expose precise photo coordinates through the query contract.

In lightweight local `eona`, a newly introduced source folder may only have world-level location state:

- country
- open sea
- supported country but dataset not installed yet
- country not supported yet

Use `location.country` for country-level questions when available.

Use `location.admin_label` and `location.admin_path` for below-country place questions. EONA may need to install or use the relevant Cadis country dataset and run scoped location semantic preparation before the final result is reliable.

### `path`

- `text`: an observed source path associated with the photo, as indexed by EONA.

Use `path.text` for fallback recall, filtering, or reporting where EONA observed a photo. Do not treat it as the stable contract for opening image bytes. When you need an actual local file path for display or downstream processing, resolve selected `photo.id` or `photo.content_id` values through the fetch surface for the runtime you are using.

## Supported Aggregations

- `count`
- `count_distinct`
- `list`
- `min`
- `max`

## Supported Operators

- `==`
- `!=`
- `>`
- `>=`
- `<`
- `<=`
- `contains`
- `in`
- `is_null`
- `is_not_null`

## Query Planning Guidance

- For broad grouping questions, prefer grouped counts plus `sort_by` and a small `limit`.
- Do not request huge result sets by default.
- Use `time.*` for time-based memory questions.
- Use `camera.*` for camera/device questions.
- Use `camera_detail.*` only for detailed camera settings/lens questions.
- Use `location.country` for country-level place questions.
- Use `location.admin_label` for below-country place questions only when location semantic enhancement is available.
- Use `path.text` only as a fallback recall query.
- If the user asks in their own language, normalize place wording into the form most likely stored in Eona before querying.

## Query-Triggered Preparation

EONA may do extra work before returning results when a query requires deferred semantic state.

Expected preparation scopes:

- `query_candidates`: EONA narrowed the query first and prepared only candidate photos
- `workspace_incremental`: EONA could not narrow first and prepared missing rows incrementally

Progress/procedure belongs in command output while the query is running. The final JSON result should remain result-focused. Treat recoverable semantic gaps in `issues` as follow-up state, not as data loss.

## Place Label Language Model

Eona stores place labels using the **local language of the place itself**, not the user's language.

This means:

- Japan → Japanese (日本語)
- Taiwan → Traditional Chinese (繁體中文)
- Italy → Italian
- France → French

These labels are derived from Cadis and reflect **local naming conventions**, not a global or user-preferred language.

### Implication for Agents

Users may ask questions using their own preferred language, which may not match how the place is stored in Eona.

Examples:

- User: "我想找在威尼斯拍的照片"
  - Stored label: `Venezia`

- User: "photos taken in Bruges"
  - Stored label: `Brugge` or `Bruges` depending on dataset

### Required Behavior

Before constructing the query, you should:

- translate or normalize the user's place wording
- convert it into the **most likely stored local label**
- then use that value in `location.admin_label` or `location.admin_path`

This is a **best-effort normalization step**, not a guaranteed mapping.

If unsure:

- prefer widely recognized local names (e.g., `Venezia`, `Kyoto`)
- or ask a clarification question when ambiguity is high

### Key Principle

- Users speak in their language
- Eona stores in the place’s language
- You bridge the gap before querying

## Time Guidance

Interpret relative time deterministically.

Use `time.year`, `time.month`, and `time.day` for calendar/date questions and date ranges. Use `time.taken_at` for timestamp ranges or ordering; it prefers the photo's original local timestamp and falls back to UTC when original time is unavailable. Use `time.hour`, `time.minute`, and `time.second` for time-of-day questions such as dawn, sunrise, sunset, morning, or evening.

Do not use raw UTC metadata for normal date ranges. Some photos have original local timestamps but no safe UTC offset, so UTC-only queries can incorrectly report dates as unknown.

Examples:

- `去年` -> previous calendar year
- `今年` -> current calendar year
- `過去五年` -> `time.year >= current_year - 4`

## Unknown Value Guidance

Use explicit null operators for unknown or known semantic fields.

- unknown year: `{"entity": "time", "attribute": "year", "operator": "is_null"}`
- known year: `{"entity": "time", "attribute": "year", "operator": "is_not_null"}`
- unknown country: `{"entity": "location", "attribute": "country", "operator": "is_null"}`
- known country: `{"entity": "location", "attribute": "country", "operator": "is_not_null"}`

Do not use `== null` or `!= null`; SQL null matching requires the explicit operators above.

## Examples

### Count photos last year

```json
{
  "query_version": 1,
  "anchor": {"entity": "photo"},
  "select": [
    {"entity": "photo", "attribute": "id", "aggregation": "count"}
  ],
  "filters": [
    {"entity": "time", "attribute": "year", "operator": "==", "value": 2025}
  ],
  "limit": 20
}
```

### Most-used camera models

```json
{
  "query_version": 1,
  "anchor": {"entity": "camera"},
  "select": [
    {"entity": "camera", "attribute": "model"},
    {"entity": "photo", "attribute": "id", "aggregation": "count"}
  ],
  "group_by": [
    {"entity": "camera", "attribute": "model"}
  ],
  "sort_by": [
    {"entity": "photo", "attribute": "id", "aggregation": "count", "order": "desc"}
  ],
  "limit": 10
}
```

### Count photos in a country

Use English for Country name, and EONA prefer full name.

```json
{
  "query_version": 1,
  "anchor": {"entity": "photo"},
  "select": [
    {"entity": "photo", "attribute": "id", "aggregation": "count"}
  ],
  "filters": [
    {"entity": "location", "attribute": "country", "operator": "==", "value": "Japan"}
  ],
  "limit": 20
}
```

### Count photos with unknown year

```json
{
  "query_version": 1,
  "anchor": {"entity": "photo"},
  "select": [
    {"entity": "photo", "attribute": "id", "aggregation": "count"}
  ],
  "filters": [
    {"entity": "time", "attribute": "year", "operator": "is_null"}
  ],
  "limit": 20
}
```

### Match place labels

Use local language for admin_label.

```json
{
  "query_version": 1,
  "anchor": {"entity": "photo"},
  "select": [
    {"entity": "photo", "attribute": "id", "aggregation": "count"}
  ],
  "filters": [
    {"entity": "location", "attribute": "admin_label", "operator": "contains", "value": "Venezia"}
  ],
  "limit": 20
}
```

## How To Answer

After Eona returns the query result:

- inspect `issues`
- inspect `result.row_count`
- inspect `result.rows` or `result.artifact`
- answer naturally from the evidence

You may:

- summarize
- rank
- sample
- reorganize
- explain uncertainty
- suggest a narrower follow-up query

Do not dump schema details unless the user actually needs them.

## Failure Handling

If Eona rejects the plan:

- correct the query if the mistake is obvious
- otherwise reduce scope to a supported query
- never switch to raw SQL

## Unsupported Semantics

Do not invent unsupported entities such as:

- `trip`
- `visit`
- `poi`

If the user asks for unsupported semantics:

- approximate with supported fields when reasonable
- otherwise say the current query surface does not directly support that dimension yet

## Summary

Your job is:

- plan Eona Query v1 JSON
- interpret the structured result
- answer the user clearly
