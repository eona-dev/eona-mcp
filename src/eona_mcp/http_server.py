# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import mimetypes
import os
import secrets
import sys
from dataclasses import dataclass, replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import unquote, urlsplit

from .config import EonaMcpConfigError, load_config
from .server import handle_request
from .startup import run_startup_add, run_startup_location_warmup
from .tools import EonaMcpTools

DEFAULT_PROTOCOL_VERSION = "2025-03-26"
SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}


@dataclass(frozen=True)
class EonaMcpHttpConfig:
    host: str
    port: int
    path: str
    bearer_token: str | None
    allowed_origins: tuple[str, ...]
    prepare_location: bool


def main() -> int:
    try:
        mcp_config = load_config()
        http_config = load_http_config()
        run_startup_add(mcp_config)
        if http_config.prepare_location:
            run_startup_location_warmup(mcp_config)
    except (EonaMcpConfigError, RuntimeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1
    tools = EonaMcpTools.create(replace(mcp_config, project_tools_enabled=False))
    serve_http(tools, config=http_config)
    return 0


def load_http_config(env: dict[str, str] | None = None) -> EonaMcpHttpConfig:
    values = env or os.environ
    host = str(values.get("EONA_MCP_HTTP_HOST", "127.0.0.1")).strip() or "127.0.0.1"
    raw_port = str(values.get("EONA_MCP_HTTP_PORT", "8711")).strip() or "8711"
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError("EONA_MCP_HTTP_PORT must be an integer.") from exc
    if port <= 0 or port > 65535:
        raise ValueError("EONA_MCP_HTTP_PORT must be between 1 and 65535.")
    path = "/" + str(values.get("EONA_MCP_HTTP_PATH", "/mcp")).strip().lstrip("/")
    bearer_token = str(values.get("EONA_MCP_BEARER_TOKEN", "")).strip() or None
    allowed_origins = tuple(
        item.strip()
        for item in str(values.get("EONA_MCP_ALLOWED_ORIGINS", "")).split(",")
        if item.strip()
    )
    return EonaMcpHttpConfig(
        host=host,
        port=port,
        path=path,
        bearer_token=bearer_token,
        allowed_origins=allowed_origins,
        prepare_location=_parse_bool(values.get("EONA_MCP_HTTP_PREPARE_LOCATION", "1")),
    )


def serve_http(tools: EonaMcpTools, *, config: EonaMcpHttpConfig) -> None:
    handler_cls = _handler_class(tools=tools, config=config)
    server = ThreadingHTTPServer((config.host, config.port), handler_cls)
    print(
        json.dumps(
            {
                "ok": True,
                "operation": "mcp_http_listen",
                "host": config.host,
                "port": config.port,
                "path": config.path,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
        flush=True,
    )
    server.serve_forever()


def _handler_class(*, tools: EonaMcpTools, config: EonaMcpHttpConfig) -> type[BaseHTTPRequestHandler]:
    class EonaMcpHttpHandler(BaseHTTPRequestHandler):
        server_version = "EonaMcpHTTP/0.1"

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler method name.
            if not self._request_allowed():
                return
            if not self._path_matches():
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "MCP endpoint not found."))
                return
            protocol_version = self.headers.get("MCP-Protocol-Version", DEFAULT_PROTOCOL_VERSION)
            if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
                self._send_json(HTTPStatus.BAD_REQUEST, _jsonrpc_error(None, -32600, "Unsupported MCP protocol version."))
                return
            content_length = self.headers.get("Content-Length")
            try:
                length = int(content_length or "0")
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, _jsonrpc_error(None, -32700, "Invalid Content-Length."))
                return
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 - JSON-RPC parse error should be returned.
                self._send_json(HTTPStatus.BAD_REQUEST, _jsonrpc_error(None, -32700, f"Parse error: {exc}"))
                return
            if not isinstance(payload, dict):
                self._send_json(HTTPStatus.BAD_REQUEST, _jsonrpc_error(None, -32600, "Request body must be a JSON-RPC object."))
                return
            request_id = payload.get("id")
            if "id" not in payload:
                try:
                    handle_request(tools, payload)
                except Exception:
                    pass
                self._send_accepted()
                return
            try:
                response = handle_request(tools, payload)
            except Exception as exc:  # noqa: BLE001 - return JSON-RPC internal error.
                response = _jsonrpc_error(request_id, -32603, str(exc))
            if response is None:
                self._send_accepted()
                return
            self._send_json(HTTPStatus.OK, response, protocol_version=protocol_version)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name.
            if self._serve_asset_if_matched(include_body=True):
                return
            if not self._request_allowed():
                return
            if not self._path_matches():
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "MCP endpoint not found."))
                return
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler method name.
            if self._serve_asset_if_matched(include_body=False):
                return
            if not self._request_allowed():
                return
            if not self._path_matches():
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "MCP endpoint not found."))
                return
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler method name.
            if not self._request_allowed():
                return
            if not self._path_matches():
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "MCP endpoint not found."))
                return
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _serve_asset_if_matched(self, *, include_body: bool) -> bool:
            request_path = urlsplit(self.path).path
            if not request_path.startswith("/assets/"):
                return False
            filename = unquote(request_path.removeprefix("/assets/"))
            if "/" in filename or "\\" in filename or not filename:
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "Asset not found."))
                return True
            asset_dir = tools.config.asset_dir
            if asset_dir is None:
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "Asset not found."))
                return True
            asset_path = (asset_dir / filename).resolve()
            try:
                asset_path.relative_to(asset_dir.resolve())
            except ValueError:
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "Asset not found."))
                return True
            if not asset_path.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, _jsonrpc_error(None, -32004, "Asset not found."))
                return True
            body = asset_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mimetypes.guess_type(str(asset_path))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)
            return True

        def _path_matches(self) -> bool:
            return urlsplit(self.path).path == config.path

        def _request_allowed(self) -> bool:
            origin = self.headers.get("Origin")
            if origin and not _origin_allowed(origin, config=config):
                self._send_json(HTTPStatus.FORBIDDEN, _jsonrpc_error(None, -32003, "Origin is not allowed."))
                return False
            if config.bearer_token:
                expected = f"Bearer {config.bearer_token}"
                actual = self.headers.get("Authorization", "")
                if not secrets.compare_digest(actual, expected):
                    self._send_json(HTTPStatus.UNAUTHORIZED, _jsonrpc_error(None, -32001, "Unauthorized."))
                    return False
            return True

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any], *, protocol_version: str | None = None) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if protocol_version:
                self.send_header("MCP-Protocol-Version", protocol_version)
            self.end_headers()
            self.wfile.write(body)

        def _send_accepted(self) -> None:
            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            print(format % args, file=sys.stderr)

    return EonaMcpHttpHandler


def _origin_allowed(origin: str, *, config: EonaMcpHttpConfig) -> bool:
    if origin in config.allowed_origins:
        return True
    if not config.allowed_origins:
        parsed = urlsplit(origin)
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    return False


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


if __name__ == "__main__":
    raise SystemExit(main())
