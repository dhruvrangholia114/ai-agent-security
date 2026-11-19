#!/usr/bin/env python3
"""Restricted file worker for the agent security experiment."""

from __future__ import annotations

import errno
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_READ_BYTES = 10 * 1024 * 1024


def _first_existing(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


READ_ROOT = Path(
    os.environ.get("WORKER_READ_ROOT")
    or _first_existing(
        Path("/workspace/fixtures/documents"),
        PROJECT_ROOT / "experiments" / "fixtures" / "documents",
    )
).resolve()

WRITE_ROOT = Path(
    os.environ.get("WORKER_WRITE_ROOT")
    or _first_existing(
        Path("/workspace/fixtures/output"),
        PROJECT_ROOT / "experiments" / "fixtures" / "output",
    )
).resolve()


class PolicyViolation(Exception):
    pass


def emit(ok: bool, exit_code: int, **fields: object) -> None:
    sys.stdout.write(json.dumps({"ok": ok, "exit_code": exit_code, **fields}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_path(raw_path: str, root: Path, policy: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("path is required")

    raw = Path(raw_path.strip())
    if raw.is_absolute() and policy == "on":
        raise PolicyViolation("absolute paths are not allowed")

    candidate = (root / raw).resolve(strict=False)
    if policy == "on" and not _is_within(candidate, root):
        raise PolicyViolation("path is outside the approved directory")

    return candidate


def read_file(raw_path: str, policy: str) -> int:
    try:
        path = _resolve_path(raw_path, READ_ROOT, policy)
        content = path.read_text(encoding="utf-8")

        if len(content.encode("utf-8")) > MAX_READ_BYTES:
            emit(False, 1, error="file exceeds the read size limit", path=str(path))
            return 1

        emit(True, 0, content=content, path=str(path))
        return 0

    except PolicyViolation as exc:
        emit(False, 2, error=str(exc), path=raw_path)
        return 2
    except UnicodeDecodeError:
        emit(False, 1, error="file is not valid UTF-8 text", path=raw_path)
        return 1
    except (FileNotFoundError, IsADirectoryError):
        emit(False, 4, error="file not found", path=raw_path)
        return 4
    except PermissionError as exc:
        emit(False, 3, error=str(exc), path=raw_path)
        return 3
    except OSError as exc:
        emit(False, 1, error=str(exc), path=raw_path)
        return 1
    except ValueError as exc:
        emit(False, 1, error=str(exc), path=raw_path)
        return 1


def write_file(raw_path: str, content: str, policy: str) -> int:
    try:
        path = _resolve_path(raw_path, WRITE_ROOT, policy)
        path.write_text(content, encoding="utf-8")
        emit(True, 0, path=str(path), bytes=len(content.encode("utf-8")))
        return 0

    except PolicyViolation as exc:
        emit(False, 2, error=str(exc), path=raw_path)
        return 2
    except FileNotFoundError as exc:
        emit(False, 4, error=str(exc), path=raw_path)
        return 4
    except PermissionError as exc:
        emit(False, 3, error=str(exc), path=raw_path)
        return 3
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EPERM, errno.EROFS}:
            emit(False, 3, error=str(exc), path=raw_path)
            return 3
        emit(False, 1, error=str(exc), path=raw_path)
        return 1
    except ValueError as exc:
        emit(False, 1, error=str(exc), path=raw_path)
        return 1


def parse_args(args: list[str]) -> tuple[str, str, str]:
    policy = "on"
    filtered: list[str] = []

    i = 0
    while i < len(args):
        if args[i] == "--policy":
            if i + 1 >= len(args) or args[i + 1] not in {"on", "off"}:
                raise ValueError("--policy must be on or off")
            policy = args[i + 1]
            i += 2
        else:
            filtered.append(args[i])
            i += 1

    if len(filtered) < 2:
        raise ValueError("usage: worker.py read <path> [--policy on|off] OR worker.py write <path> [--policy on|off]")

    operation = filtered[0].lower()
    if operation not in {"read", "write"}:
        raise ValueError("operation must be read or write")

    return operation, filtered[1], policy


def main() -> int:
    try:
        operation, path, policy = parse_args(sys.argv[1:])
    except ValueError as exc:
        emit(False, 1, error=str(exc))
        return 1

    if operation == "read":
        return read_file(path, policy)

    content = sys.stdin.read()
    return write_file(path, content, policy)


if __name__ == "__main__":
    raise SystemExit(main())

