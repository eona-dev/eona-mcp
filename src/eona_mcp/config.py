# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_QUERY_RESOURCE_PATH = Path("agent/EONA-Query-v1.md")


class EonaMcpConfigError(ValueError):
    pass


@dataclass(frozen=True)
class EonaMcpConfig:
    project_id: str
    session_id: str
    workspace: Path | None
    sources: tuple[str, ...]
    project_description: str | None = None
    eona_executable: str = "eona"
    startup_add: bool = True
    startup_required: bool = True
    project_tools_enabled: bool = False
    query_resource_path: Path = DEFAULT_QUERY_RESOURCE_PATH
    asset_dir: Path | None = None
    asset_base_url: str | None = None

    @property
    def tool_prefix(self) -> str:
        return f"eona.{self.project_id}"


def load_config(env: Mapping[str, str] | None = None) -> EonaMcpConfig:
    values = env or os.environ
    project_id = _required_project_id(values.get("EONA_PROJECT_ID", "default"))
    session_id = _required_project_id(values.get("EONA_SESSION_ID") or project_id)
    sources = _parse_sources(values.get("EONA_SOURCES_JSON"))
    family_root = Path(values.get("EONA_FAMILY_ROOT") or Path.home() / ".eona").expanduser().resolve()
    workspace = Path(values.get("EONA_MCP_WORKSPACE") or family_root / "workspace").expanduser().resolve()
    cli_root = Path(values.get("EONA_CLI_INSTALL_ROOT") or family_root / "eona-cli").expanduser().resolve()
    return EonaMcpConfig(
        project_id=project_id,
        session_id=session_id,
        workspace=workspace,
        sources=sources,
        project_description=_optional_text(values.get("EONA_PROJECT_DESCRIPTION")),
        eona_executable=str(values.get("EONA_CLI") or (cli_root / "bin" / "eona")),
        startup_add=_parse_bool(values.get("EONA_STARTUP_ADD", "1")),
        startup_required=_parse_bool(values.get("EONA_STARTUP_REQUIRED", "1")),
        project_tools_enabled=True,
        query_resource_path=_resource_path(
            values,
            env_key="EONA_QUERY_RESOURCE_PATH",
            default_path=DEFAULT_QUERY_RESOURCE_PATH,
        ),
        asset_dir=_optional_path(
            values.get("EONA_MCP_ASSET_DIR"),
            default=workspace / "assets",
        ),
        asset_base_url=_optional_text(values.get("EONA_MCP_ASSET_BASE_URL")),
    )


def _required_project_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not PROJECT_ID_PATTERN.fullmatch(normalized):
        raise EonaMcpConfigError(
            "EONA project/session id must start with an ASCII letter or digit and contain only "
            "ASCII letters, digits, '.', '_', or '-'."
        )
    return normalized


def _parse_sources(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None or not str(raw_value).strip():
        return ()
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise EonaMcpConfigError("EONA_SOURCES_JSON must be a JSON array of source paths.") from exc
    if not isinstance(payload, list):
        raise EonaMcpConfigError("EONA_SOURCES_JSON must be a JSON array of source paths.")
    sources = tuple(str(item).strip() for item in payload if str(item).strip())
    return sources


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _optional_text(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _optional_path(value: str | None, *, default: Path | None = None) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return default
    return Path(raw).expanduser().resolve()


def _resource_path(values: Mapping[str, str], *, env_key: str, default_path: Path) -> Path:
    path = Path(values.get(env_key, str(default_path)))
    if path.is_absolute():
        return path
    release_root = str(values.get("EONA_RELEASE_ROOT", "")).strip()
    if release_root:
        return Path(release_root) / path
    return path
