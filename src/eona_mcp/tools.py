# SPDX-License-Identifier: MIT
from __future__ import annotations

import mimetypes
import json
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .cli import EonaCliInvocationError, EonaCliRunner
from .config import EonaMcpConfig

QUERY_GUIDE_URI = "eona://agent/how-to-query"
FETCH_GUIDE_URI = "eona://agent/how-to-fetch-photos"
QUERY_FORMAT_GUIDANCE = (
    "Please read MCP resource eona://agent/how-to-query before retrying. "
    "The query tool requires an Eona Query v1 plan with query_version=1, "
    "anchor={\"entity\":\"photo\"}, select, and supported entities/attributes/operators only."
)
FETCH_FORMAT_GUIDANCE = (
    "Please read MCP resource eona://agent/how-to-fetch-photos before retrying. "
    "The fetch tool requires EONA photo.id values in `photo_ids`; never pass source file paths."
)
DEFAULT_FETCH_MAX_BYTES = 12 * 1024 * 1024
FETCH_MAX_PHOTOS = 4


@dataclass(frozen=True)
class EonaMcpTools:
    config: EonaMcpConfig
    runner: EonaCliRunner

    @classmethod
    def create(cls, config: EonaMcpConfig) -> "EonaMcpTools":
        return cls(config=config, runner=EonaCliRunner(config))

    def list_tools(self) -> list[dict[str, Any]]:
        prefix = self.config.tool_prefix
        return [
            {
                "name": f"{prefix}.append",
                "description": (
                    "Append local photo source paths to this MCP project's EONA session. "
                    "By default use refresh=false. Set refresh=true only after the user explicitly asks "
                    "to rescan or update photo metadata, because refresh can take a long time."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["sources"],
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Local photo folder paths to attach to the project session.",
                        },
                        "refresh": {
                            "type": "boolean",
                            "default": False,
                            "description": (
                                "Keep false unless the user explicitly confirms a rescan/update. "
                                "When true, EONA may scan and refresh photo metadata for the requested folders."
                            ),
                        },
                    },
                    "additionalProperties": False,
                },
            },
            {"name": f"{prefix}.list", "description": "List source roots in this MCP project session.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": f"{prefix}.reset", "description": "Reset this MCP project session without deleting source photos.", "inputSchema": {"type": "object", "required": ["confirm"], "properties": {"confirm": {"type": "boolean"}}, "additionalProperties": False}},
            {"name": f"{prefix}.refresh", "description": "Refresh all source roots in this MCP project session. Use only when the user explicitly asks to rescan/update existing photo metadata.", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": f"{prefix}.query", "description": "Query metadata and Cadis-enriched photo memory for this MCP project session.", "inputSchema": {"type": "object", "required": ["plan"], "properties": {"plan": {"type": "object"}, "in_sources": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": False}},
            {
                "name": f"{prefix}.fetch",
                "description": (
                    "Fetch one or more indexed photos by EONA photo.id. "
                    "Read resource eona://agent/how-to-fetch-photos before calling this tool. "
                    "Do not pass file paths."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["photo_ids"],
                    "properties": {
                        "photo_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "EONA photo.id values returned by the query tool.",
                        },
                        "max_bytes": {
                            "type": "integer",
                            "default": DEFAULT_FETCH_MAX_BYTES,
                            "description": "Maximum bytes per photo to return.",
                        },
                    },
                    "additionalProperties": False,
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        args = arguments or {}
        prefix = self.config.tool_prefix
        try:
            if name == f"{prefix}.query":
                plan = args.get("plan")
                if not isinstance(plan, dict):
                    return _query_format_error("`plan` must be an object.")
                plan_error = _validate_query_plan_shape(plan)
                if plan_error:
                    return _query_format_error(plan_error)
                try:
                    return _tool_result(self.runner.query(plan=plan, in_sources=_string_list(args.get("in_sources"))))
                except EonaCliInvocationError as exc:
                    if _looks_like_query_format_error(exc):
                        return _query_format_error(
                            "EONA CLI rejected the query plan format.",
                            payload={"returncode": exc.returncode, "stdout": exc.stdout, "stderr": exc.stderr},
                        )
                    raise
            if name == f"{prefix}.fetch":
                photo_ids = _string_list(args.get("photo_ids"))
                if not photo_ids:
                    return _fetch_format_error("`photo_ids` must include at least one EONA photo.id.")
                if _looks_like_path_values(photo_ids):
                    return _fetch_format_error("`photo_ids` must contain EONA photo.id values, not file paths.")
                if len(photo_ids) > FETCH_MAX_PHOTOS:
                    return _fetch_format_error(f"`photo_ids` may include at most {FETCH_MAX_PHOTOS} photo id(s) per fetch call.")
                max_bytes = _positive_int(args.get("max_bytes"), DEFAULT_FETCH_MAX_BYTES)
                return _fetch_photos(self, photo_ids=photo_ids, max_bytes=max_bytes)
            if name == f"{prefix}.append":
                sources = _string_list(args.get("sources"))
                if not sources:
                    return _tool_error("`sources` must include at least one source path.")
                return _tool_result(self.runner.add(sources=sources, refresh=bool(args.get("refresh", False)), stream_stderr=True))
            if name == f"{prefix}.list":
                return _tool_result(self.runner.list_session_sources())
            if name == f"{prefix}.reset":
                if args.get("confirm") is not True:
                    return _tool_error("`confirm` must be true to reset this project session.")
                return _tool_result(self.runner.reset_session())
            if name == f"{prefix}.refresh":
                return _tool_result(self.runner.refresh_session())
        except EonaCliInvocationError as exc:
            return _tool_error(str(exc), payload={"returncode": exc.returncode, "stdout": exc.stdout, "stderr": exc.stderr})
        return _tool_error(f"Unknown EONA MCP tool: {name}")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, sort_keys=True),
            }
        ],
        "isError": False,
    }


def _tool_error(message: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"ok": False, "error": message}
    if payload:
        body.update(payload)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(body, sort_keys=True),
            }
        ],
        "isError": True,
    }


def _query_format_error(message: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "query_resource_uri": QUERY_GUIDE_URI,
        "retry_instruction": QUERY_FORMAT_GUIDANCE,
    }
    if payload:
        body.update(payload)
    return _tool_error(f"{message} {QUERY_FORMAT_GUIDANCE}", payload=body)


def _fetch_format_error(message: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = {
        "fetch_resource_uri": FETCH_GUIDE_URI,
        "retry_instruction": FETCH_FORMAT_GUIDANCE,
    }
    if payload:
        body.update(payload)
    return _tool_error(f"{message} {FETCH_FORMAT_GUIDANCE}", payload=body)


def _validate_query_plan_shape(plan: dict[str, Any]) -> str | None:
    if plan.get("query_version") != 1:
        return "`plan.query_version` must be 1."
    anchor = plan.get("anchor")
    if not isinstance(anchor, dict):
        return "`plan.anchor` must be an object such as {\"entity\":\"photo\"}."
    if not isinstance(anchor.get("entity"), str) or not anchor["entity"].strip():
        return "`plan.anchor.entity` must be a non-empty string such as \"photo\"."
    select = plan.get("select")
    if not isinstance(select, list) or not select:
        return "`plan.select` must be a non-empty array of typed entity selections."
    return None


def _looks_like_query_format_error(exc: EonaCliInvocationError) -> bool:
    text = f"{exc.stdout}\n{exc.stderr}".lower()
    markers = (
        "query_version",
        "anchor",
        "select",
        "filter",
        "group_by",
        "sort_by",
        "operator",
        "aggregation",
        "attribute",
        "entity",
        "schema",
        "validation",
        "unsupported",
        "unknown",
        "invalid",
    )
    return any(marker in text for marker in markers)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _looks_like_path_values(values: list[str]) -> bool:
    return any(
        "/" in value
        or "\\" in value
        or value.startswith(".")
        or value.startswith("~")
        for value in values
    )


def _fetch_photos(tools: EonaMcpTools, *, photo_ids: list[str], max_bytes: int) -> dict[str, Any]:
    allowed_roots = _allowed_source_roots(tools.config.sources)
    if not allowed_roots:
        return _tool_error("No configured EONA source roots are available for photo fetch.")
    rows = _resolve_photo_paths(tools, photo_ids)
    rows_by_id = {_row_value(row, "id"): row for row in rows if _row_value(row, "id")}
    content: list[dict[str, Any]] = []
    fetched: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for photo_id in photo_ids:
        row = rows_by_id.get(photo_id)
        if row is None:
            failed.append({"photo_id": photo_id, "error": "Photo id was not found in this EONA project."})
            continue
        path_text = _row_value(row, "text") or _row_value(row, "path")
        path = Path(path_text).expanduser() if path_text else None
        if path is None or not path.is_file():
            failed.append({"photo_id": photo_id, "error": "Resolved photo path is not readable."})
            continue
        resolved_path = path.resolve()
        if not _path_under_any_root(resolved_path, allowed_roots):
            failed.append({"photo_id": photo_id, "error": "Resolved photo path is outside configured source roots."})
            continue
        size = resolved_path.stat().st_size
        if size > max_bytes:
            failed.append({"photo_id": photo_id, "error": "Photo exceeds max_bytes.", "byte_size": size, "max_bytes": max_bytes})
            continue
        mime_type = mimetypes.guess_type(str(resolved_path))[0] or "application/octet-stream"
        item = {
            "photo_id": photo_id,
            "content_id": _row_value(row, "content_id") or None,
            "mime_type": mime_type,
            "byte_size": size,
        }
        asset = _publish_asset(tools, source_path=resolved_path)
        if asset is not None:
            item.update(asset)
        else:
            failed.append({"photo_id": photo_id, "error": "No EONA asset directory is configured for photo fetch."})
            continue
        fetched.append(item)
    content.insert(
        0,
        {
            "type": "text",
            "text": json.dumps(
                {
                    "ok": not failed,
                    "fetched": fetched,
                    "failed": failed,
                    "max_photos": FETCH_MAX_PHOTOS,
                },
                sort_keys=True,
            ),
        },
    )
    return {"content": content, "isError": bool(failed) and not fetched}


def _publish_asset(tools: EonaMcpTools, *, source_path: Path) -> dict[str, str] | None:
    asset_base_url = str(tools.config.asset_base_url or "").strip().rstrip("/")
    asset_dir = tools.config.asset_dir
    if asset_dir is None:
        return None
    asset_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()
    if len(suffix) > 16 or not suffix.startswith("."):
        suffix = ""
    filename = f"{secrets.token_urlsafe(24)}{suffix}"
    asset_path = asset_dir / filename
    shutil.copyfile(source_path, asset_path)
    url = f"{asset_base_url}/{filename}" if asset_base_url else _file_url(asset_path)
    return {
        "asset_path": str(asset_path),
        "url": url,
    }


def _file_url(path: Path) -> str:
    return "file://" + quote(str(path.resolve()))


def _resolve_photo_paths(tools: EonaMcpTools, photo_ids: list[str]) -> list[dict[str, Any]]:
    plan = {
        "query_version": 1,
        "anchor": {"entity": "photo"},
        "select": [
            {"entity": "photo", "attribute": "id"},
            {"entity": "photo", "attribute": "content_id"},
            {"entity": "path", "attribute": "text"},
        ],
        "filters": [
            {"entity": "photo", "attribute": "id", "operator": "in", "value": photo_ids},
        ],
        "limit": len(photo_ids),
    }
    payload = tools.runner.query(plan=plan)
    result = payload.get("result")
    rows = result.get("rows") if isinstance(result, dict) else payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _allowed_source_roots(sources: tuple[str, ...]) -> list[Path]:
    roots: list[Path] = []
    for source in sources:
        path = Path(source).expanduser()
        if path.is_dir():
            roots.append(path.resolve())
        elif path.is_file():
            roots.append(path.resolve().parent)
    return roots


def _path_under_any_root(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
        except ValueError:
            continue
        return True
    return False


def _row_value(row: dict[str, Any], attribute: str) -> str:
    candidate_keys = (
        attribute,
        f"photo.{attribute}",
        f"photo_{attribute}",
        f"path.{attribute}",
        f"path_{attribute}",
    )
    for key in candidate_keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key, value in row.items():
        if str(key).endswith(attribute) and isinstance(value, str) and value.strip():
            return value.strip()
    return ""
