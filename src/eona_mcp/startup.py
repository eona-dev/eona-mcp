# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import sys
from typing import Any

from .cli import EonaCliInvocationError, EonaCliRunner
from .config import EonaMcpConfig


def run_startup_add(config: EonaMcpConfig, runner: EonaCliRunner | None = None) -> dict[str, Any] | None:
    if not config.startup_add:
        return None
    if not config.sources:
        return None
    resolved_runner = runner or EonaCliRunner(config)
    try:
        result = resolved_runner.add(
            sources=config.sources,
            source_roots=config.source_roots,
            refresh=False,
            stream_stderr=True,
        )
    except EonaCliInvocationError as exc:
        failure = {
            "ok": False,
            "operation": "startup_add",
            "summary": str(exc),
            "returncode": exc.returncode,
            "stdout": exc.stdout,
            "stderr": exc.stderr,
        }
        _log_startup_event(failure)
        if config.startup_required:
            raise
        return failure
    _log_startup_event(
        {
            "ok": True,
            "operation": "startup_add",
            "project_id": config.project_id,
            "session_id": config.session_id,
            "sources": list(config.sources),
            "source_roots": list(config.source_roots),
            "result": result,
        }
    )
    return result


def _log_startup_event(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)
