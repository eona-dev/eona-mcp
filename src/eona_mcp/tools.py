# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .cli import EonaCliInvocationError, EonaCliRunner
from .config import EonaMcpConfig

QUERY_GUIDE_URI = "eona://agent/how-to-query"
QUERY_FORMAT_GUIDANCE = (
    "Please read MCP resource eona://agent/how-to-query before retrying. "
    "The query tool requires an Eona Query v1 plan with query_version=1, "
    "anchor={\"entity\":\"photo\"}, select, and supported entities/attributes/operators only."
)


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
            {
                "name": f"{prefix}.query",
                "description": (
                    "Query metadata and Cadis-enriched photo memory for this MCP project session. "
                    "Before complex queries, read resource eona://agent/how-to-query. "
                    "The plan must be Eona Query v1: include query_version=1, "
                    "anchor={\"entity\":\"photo\"}, select, and optional filters/sort_by/limit. "
                    "Supported fields include photo.id/content_id, path.text, time.taken_at/year/month/day, "
                    "location.country/admin_label/admin_path, camera.make/model, and camera_detail lens/settings. "
                    "Use aggregation inside select/sort_by items, for example "
                    "{\"entity\":\"photo\",\"attribute\":\"id\",\"aggregation\":\"count\"}. "
                    "Do not request filename, filepath, raw GPS, trips, albums, or SQL. "
                    "Do not write SQL."
                ),
                "inputSchema": {
                    "type": "object",
                    "required": ["plan"],
                    "properties": {
                        "plan": {
                            "type": "object",
                            "description": (
                                "Eona Query v1 plan. Example: "
                                "{\"query_version\":1,\"anchor\":{\"entity\":\"photo\"},"
                                "\"select\":[{\"entity\":\"time\",\"attribute\":\"taken_at\"},"
                                "{\"entity\":\"location\",\"attribute\":\"admin_path\"}],"
                                "\"filters\":[{\"entity\":\"location\",\"attribute\":\"admin_path\","
                                "\"operator\":\"contains\",\"value\":\"Rotterdam\"}],"
                                "\"sort_by\":[{\"entity\":\"time\",\"attribute\":\"taken_at\","
                                "\"order\":\"desc\"}],\"limit\":10}"
                            ),
                            "required": ["query_version", "anchor", "select"],
                            "properties": {
                                "query_version": {"type": "integer", "const": 1},
                                "anchor": {
                                    "type": "object",
                                    "required": ["entity"],
                                    "properties": {"entity": {"type": "string"}},
                                },
                                "select": {"type": "array", "items": {"type": "object"}},
                                "filters": {"type": "array", "items": {"type": "object"}},
                                "group_by": {"type": "array", "items": {"type": "object"}},
                                "sort_by": {"type": "array", "items": {"type": "object"}},
                                "limit": {"type": ["integer", "null"]},
                            },
                            "additionalProperties": True,
                        },
                        "in_sources": {"type": "array", "items": {"type": "string"}},
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
