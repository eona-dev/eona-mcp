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
            "result": result,
        }
    )
    return result


def run_startup_location_warmup(config: EonaMcpConfig, runner: EonaCliRunner | None = None) -> dict[str, Any]:
    resolved_runner = runner or EonaCliRunner(config)
    try:
        country_result = resolved_runner.query(plan=_country_discovery_plan(), stream_stderr=True)
    except EonaCliInvocationError as exc:
        failure = _startup_cli_failure("startup_location_warmup", exc)
        _log_startup_event(failure)
        if config.startup_required:
            raise
        return failure

    countries = _countries_from_query_result(country_result)
    warmed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    _log_startup_event(
        {
            "ok": True,
            "operation": "startup_location_warmup_countries",
            "project_id": config.project_id,
            "session_id": config.session_id,
            "countries": countries,
            "country_count": len(countries),
        }
    )
    for country in countries:
        try:
            result = resolved_runner.query(plan=_admin_location_warmup_plan(country), stream_stderr=True)
        except EonaCliInvocationError as exc:
            item = {
                "country": country,
                "returncode": exc.returncode,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            }
            failed.append(item)
            _log_startup_event(
                {
                    "ok": False,
                    "operation": "startup_location_warmup_country",
                    "project_id": config.project_id,
                    "session_id": config.session_id,
                    **item,
                }
            )
            if config.startup_required:
                raise
            continue
        row_count = _query_row_count(result)
        item = {"country": country, "row_count": row_count}
        warmed.append(item)
        _log_startup_event(
            {
                "ok": True,
                "operation": "startup_location_warmup_country",
                "project_id": config.project_id,
                "session_id": config.session_id,
                **item,
            }
        )
    summary = {
        "ok": not failed,
        "operation": "startup_location_warmup",
        "project_id": config.project_id,
        "session_id": config.session_id,
        "country_count": len(countries),
        "warmed": warmed,
        "failed": failed,
    }
    _log_startup_event(summary)
    return summary


def _log_startup_event(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, sort_keys=True), file=sys.stderr, flush=True)


def _startup_cli_failure(operation: str, exc: EonaCliInvocationError) -> dict[str, Any]:
    return {
        "ok": False,
        "operation": operation,
        "summary": str(exc),
        "returncode": exc.returncode,
        "stdout": exc.stdout,
        "stderr": exc.stderr,
    }


def _country_discovery_plan() -> dict[str, Any]:
    return {
        "query_version": 1,
        "anchor": {"entity": "photo"},
        "select": [
            {"entity": "location", "attribute": "country"},
            {"entity": "photo", "attribute": "id", "aggregation": "count"},
        ],
        "filters": [
            {"entity": "location", "attribute": "country", "operator": "is_not_null"},
        ],
        "group_by": [
            {"entity": "location", "attribute": "country"},
        ],
        "sort_by": [
            {"entity": "photo", "attribute": "id", "aggregation": "count", "order": "desc"},
        ],
        "limit": None,
    }


def _admin_location_warmup_plan(country: str) -> dict[str, Any]:
    return {
        "query_version": 1,
        "anchor": {"entity": "photo"},
        "select": [
            {"entity": "location", "attribute": "admin_path"},
            {"entity": "location", "attribute": "admin_label"},
            {"entity": "photo", "attribute": "id", "aggregation": "count"},
        ],
        "filters": [
            {"entity": "location", "attribute": "country", "operator": "==", "value": country},
        ],
        "group_by": [
            {"entity": "location", "attribute": "admin_path"},
            {"entity": "location", "attribute": "admin_label"},
        ],
        "sort_by": [
            {"entity": "photo", "attribute": "id", "aggregation": "count", "order": "desc"},
        ],
        "limit": None,
    }


def _countries_from_query_result(payload: dict[str, Any]) -> list[str]:
    countries: list[str] = []
    seen: set[str] = set()
    for row in _query_rows(payload):
        country = _row_value(row, "country")
        if not country:
            continue
        if country in seen:
            continue
        seen.add(country)
        countries.append(country)
    return countries


def _query_row_count(payload: dict[str, Any]) -> int:
    result = payload.get("result")
    if isinstance(result, dict):
        row_count = result.get("row_count")
        if isinstance(row_count, int):
            return row_count
    return len(_query_rows(payload))


def _query_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    rows = result.get("rows") if isinstance(result, dict) else payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _row_value(row: dict[str, Any], attribute: str) -> str:
    candidate_keys = (
        attribute,
        f"location.{attribute}",
        f"location_{attribute}",
    )
    for key in candidate_keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key, value in row.items():
        if str(key).endswith(attribute) and isinstance(value, str) and value.strip():
            return value.strip()
    return ""
