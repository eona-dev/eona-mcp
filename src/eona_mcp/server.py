# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from .config import EonaMcpConfigError, load_config
from .startup import run_startup_add
from .tools import EonaMcpTools

JSONRPC_VERSION = "2.0"
QUERY_GUIDE_URI = "eona://agent/how-to-query"
FETCH_GUIDE_URI = "eona://agent/how-to-fetch-photos"


def main() -> int:
    try:
        config = load_config()
        run_startup_add(config)
    except (EonaMcpConfigError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    return serve(EonaMcpTools.create(config))


def serve(tools: EonaMcpTools, *, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
    input_handle = input_stream or sys.stdin
    output_handle = output_stream or sys.stdout
    for line in input_handle:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = handle_request(tools, request)
        except Exception as exc:
            response = _error_response(None, -32603, str(exc))
        if response is not None:
            print(json.dumps(response, separators=(",", ":")), file=output_handle, flush=True)
    return 0


def handle_request(tools: EonaMcpTools, request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = str(request.get("method") or "")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    if method == "initialize":
        return _result_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": "eona-mcp", "version": "0.0.18"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _result_response(request_id, {"tools": tools.list_tools()})
    if method == "tools/call":
        tool_name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        return _result_response(request_id, tools.call_tool(tool_name, arguments))
    if method == "resources/list":
        return _result_response(request_id, {"resources": [_query_guide_resource(tools), _fetch_guide_resource(tools)]})
    if method == "resources/read":
        uri = str(params.get("uri") or "")
        if uri == QUERY_GUIDE_URI:
            return _result_response(request_id, {"contents": [_read_query_guide(tools)]})
        if uri == FETCH_GUIDE_URI:
            return _result_response(request_id, {"contents": [_read_fetch_guide(tools)]})
        return _error_response(request_id, -32602, f"Unknown resource: {uri}")
    if method == "ping":
        return _result_response(request_id, {})
    return _error_response(request_id, -32601, f"Method not found: {method}")


def _result_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _query_guide_resource(tools: EonaMcpTools) -> dict[str, Any]:
    project_context = ""
    if tools.config.project_description:
        project_context = f" Project context: {tools.config.project_description.strip().rstrip('.')}."
    return {
        "uri": QUERY_GUIDE_URI,
        "name": "How to Query with Eona",
        "description": (
            "Required guide for translating natural-language photo-library questions into "
            "Eona Query v1 JSON plans."
            f"{project_context} "
            "Read this before calling the EONA query tool; prefer "
            "the tool over filesystem searches for indexed photos."
        ),
        "mimeType": "text/markdown",
    }


def _fetch_guide_resource(tools: EonaMcpTools) -> dict[str, Any]:
    project_context = ""
    if tools.config.project_description:
        project_context = f" Project context: {tools.config.project_description.strip().rstrip('.')}."
    return {
        "uri": FETCH_GUIDE_URI,
        "name": "How to Fetch Photos with Eona MCP",
        "description": (
            "Required guide for showing or sending EONA photos through MCP. "
            "Read this before calling the EONA fetch tool; use photo.id values, "
            "never source file paths."
            f"{project_context}"
        ),
        "mimeType": "text/markdown",
    }


def _read_query_guide(tools: EonaMcpTools) -> dict[str, Any]:
    path = tools.config.query_resource_path
    text = path.read_text(encoding="utf-8")
    return {
        "uri": QUERY_GUIDE_URI,
        "mimeType": "text/markdown",
        "text": text,
    }


def _read_fetch_guide(tools: EonaMcpTools) -> dict[str, Any]:
    path = tools.config.fetch_resource_path
    text = path.read_text(encoding="utf-8")
    return {
        "uri": FETCH_GUIDE_URI,
        "mimeType": "text/markdown",
        "text": text,
    }


if __name__ == "__main__":
    raise SystemExit(main())
