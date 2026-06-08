# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Any

from .config import EonaMcpConfig


class EonaCliInvocationError(RuntimeError):
    def __init__(self, *, command: list[str], returncode: int, stdout: str, stderr: str) -> None:
        super().__init__(f"EONA CLI command failed with exit code {returncode}: {' '.join(command)}")
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class EonaCliRunner:
    config: EonaMcpConfig

    def add(
        self,
        *,
        sources: list[str] | tuple[str, ...] | None = None,
        refresh: bool = False,
        stream_stderr: bool = False,
    ) -> dict[str, Any]:
        command = self._base_command("add")
        resolved_sources = _source_args(self.config.sources if sources is None else sources)
        for source in resolved_sources:
            command.extend(["--source", source])
        if refresh:
            command.append("--refresh")
        return self._run_json(command, stream_stderr=stream_stderr)

    def query(
        self,
        *,
        plan: dict[str, Any],
        in_sources: list[str] | tuple[str, ...] | None = None,
        stream_stderr: bool = False,
    ) -> dict[str, Any]:
        command = self._base_command("query")
        command.extend(["--input", "-"])
        for source in _source_args(in_sources or ()):
            command.extend(["--in-source", source])
        payload = self._run_json(command, stdin=json.dumps(plan, separators=(",", ":")), stream_stderr=stream_stderr)
        return _inline_query_artifact(payload)

    def reset_session(self) -> dict[str, Any]:
        command = [
            self.config.eona_executable,
            "session",
            "reset",
            "--session-id",
            self.config.session_id,
            "--confirm",
            "--json",
        ]
        if self.config.workspace is not None:
            command[3:3] = ["--workspace", str(self.config.workspace)]
        return self._run_json(command)

    def list_session_sources(self) -> dict[str, Any]:
        command = [
            self.config.eona_executable,
            "session",
            "sources",
            "--session-id",
            self.config.session_id,
            "--json",
        ]
        if self.config.workspace is not None:
            command[3:3] = ["--workspace", str(self.config.workspace)]
        return self._run_json(command)

    def refresh_session(self) -> dict[str, Any]:
        command = [
            self.config.eona_executable,
            "session",
            "refresh",
            "--session-id",
            self.config.session_id,
            "--json",
        ]
        if self.config.workspace is not None:
            command[3:3] = ["--workspace", str(self.config.workspace)]
        return self._run_json(command, stream_stderr=True)

    def fetch(
        self,
        *,
        photo_ids: list[str] | tuple[str, ...] | None = None,
        content_ids: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        command = self._base_command("fetch")
        for photo_id in _source_args(photo_ids or ()):
            command.extend(["--photo-id", photo_id])
        for content_id in _source_args(content_ids or ()):
            command.extend(["--content-id", content_id])
        return self._run_json(command)

    def _base_command(self, subcommand: str) -> list[str]:
        command = [
            self.config.eona_executable,
            subcommand,
            "--session-id",
            self.config.session_id,
            "--json",
        ]
        if self.config.workspace is not None:
            command[2:2] = ["--workspace", str(self.config.workspace)]
        return command

    def _run_json(self, command: list[str], *, stdin: str | None = None, stream_stderr: bool = False) -> dict[str, Any]:
        if stream_stderr:
            returncode, stdout, stderr = _run_capturing_stdout_and_streaming_stderr(command, stdin=stdin)
        else:
            completed = subprocess.run(
                command,
                input=stdin,
                text=True,
                capture_output=True,
                check=False,
            )
            returncode = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        if returncode != 0:
            raise EonaCliInvocationError(
                command=command,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise EonaCliInvocationError(
                command=command,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr or str(exc),
            ) from exc
        if not isinstance(payload, dict):
            raise EonaCliInvocationError(
                command=command,
                returncode=returncode,
                stdout=stdout,
                stderr="EONA CLI returned non-object JSON.",
            )
        return payload


def _run_capturing_stdout_and_streaming_stderr(command: list[str], *, stdin: str | None = None) -> tuple[int, str, str]:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stderr_chunks: list[str] = []

    def drain_stderr() -> None:
        assert process.stderr is not None
        for chunk in iter(process.stderr.readline, ""):
            stderr_chunks.append(chunk)
            print(chunk, end="", file=sys.stderr, flush=True)

    stderr_thread = Thread(target=drain_stderr, daemon=True)
    stderr_thread.start()
    if stdin is not None:
        assert process.stdin is not None
        try:
            process.stdin.write(stdin)
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()
    assert process.stdout is not None
    stdout = process.stdout.read()
    process.wait()
    stderr_thread.join()
    return process.returncode, stdout or "", "".join(stderr_chunks)


def _source_args(values: list[str] | tuple[str, ...]) -> list[str]:
    return [str(item).strip() for item in values if str(item).strip()]


def _inline_query_artifact(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get("result")
    if not isinstance(result, dict):
        return payload
    if isinstance(result.get("rows"), list):
        return payload
    artifact = result.get("artifact")
    if not isinstance(artifact, dict):
        return payload
    artifact_path = artifact.get("path")
    if not isinstance(artifact_path, str) or not artifact_path.strip():
        return payload
    try:
        artifact_payload = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - preserve the query result and expose transport context.
        result["artifact_inline_error"] = str(exc)
        return payload
    rows = _artifact_rows(artifact_payload)
    if rows is None:
        result["artifact_inline_error"] = "Artifact JSON did not contain query rows."
        return payload
    result["rows"] = rows
    result["artifact_inlined"] = True
    result.pop("artifact", None)
    return payload


def _artifact_rows(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    if isinstance(payload, dict) and isinstance(payload.get("result"), dict):
        rows = payload["result"].get("rows")
        if isinstance(rows, list):
            return rows
    return None
