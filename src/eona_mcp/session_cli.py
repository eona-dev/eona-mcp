# SPDX-License-Identifier: MIT
from __future__ import annotations

import argparse
import json
from typing import Any

from .cli import EonaCliRunner
from .config import EonaMcpConfig, load_config


def list_sources(config: EonaMcpConfig) -> dict[str, Any]:
    return EonaCliRunner(config).list_session_sources()


def reset_session(config: EonaMcpConfig) -> dict[str, Any]:
    return EonaCliRunner(config).reset_session()


def refresh_session(config: EonaMcpConfig) -> dict[str, Any]:
    return EonaCliRunner(config).refresh_session()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eona-session")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list").add_argument("--json", action="store_true")
    reset_parser = subparsers.add_parser("reset")
    reset_parser.add_argument("--confirm", action="store_true", required=True)
    reset_parser.add_argument("--json", action="store_true")
    subparsers.add_parser("refresh").add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    config = load_config()
    if args.command == "list":
        payload = list_sources(config)
    elif args.command == "reset":
        payload = reset_session(config)
    elif args.command == "refresh":
        payload = refresh_session(config)
    else:
        raise RuntimeError(args.command)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
