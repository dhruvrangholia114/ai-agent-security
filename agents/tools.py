"""CrewAI tools for launching the restricted file worker."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from crewai.tools import tool


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCRIPT_PATHS = {
    "standard": PROJECT_ROOT / "sandbox" / "standard" / "run-standard.sh",
    "hardened": PROJECT_ROOT / "sandbox" / "hardened" / "run-hardened.sh",
    "gvisor": PROJECT_ROOT / "sandbox" / "gvisor" / "run-gvisor-hardened.sh",
}


def _append_trial(trial_log: Path, record: dict[str, object]) -> None:
    trial_log.parent.mkdir(parents=True, exist_ok=True)
    with trial_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _trial_record(
    *,
    trial_id: str,
    tool: str,
    agent_env: str,
    policy: str,
    op: str,
    path: str,
    status: str,
    elapsed_ms: float,
    exit_code: int | None,
    **fields: object,
) -> dict[str, object]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trial_id": trial_id,
        "tool": tool,
        "env": agent_env,
        "policy": policy,
        "op": op,
        "path": path,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "exit_code": exit_code,
        **fields,
    }


def run_worker(op: str, path: str, content: str = "", tool: str = "") -> str:
    """Run one read/write request in the selected sandbox environment."""

    agent_env = os.environ.get("AGENT_ENV")
    policy = os.environ.get("AGENT_POLICY")
    trial_log_value = os.environ.get("TRIAL_LOG")
    trial_id = os.environ.get("TRIAL_ID")

    if not agent_env:
        raise RuntimeError("AGENT_ENV is required")
    if agent_env not in SCRIPT_PATHS:
        raise RuntimeError("AGENT_ENV must be one of: standard, hardened, gvisor")
    if not policy:
        raise RuntimeError("AGENT_POLICY is required")
    if policy not in {"on", "off"}:
        raise RuntimeError("AGENT_POLICY must be exactly 'on' or 'off'")
    if not trial_log_value:
        raise RuntimeError("TRIAL_LOG is required")
    if not trial_id:
        raise RuntimeError("TRIAL_ID is required")

    trial_log = Path(trial_log_value)
    tool_name = tool or "run_worker"
    started = time.perf_counter()

    try:
        script = SCRIPT_PATHS[agent_env]
        completed = subprocess.run(
            [
                str(script),
                "python",
                "agents/worker.py",
                op,
                path,
                "--policy",
                policy,
            ],
            input=content,
            capture_output=True,
            text=True,
            timeout=30,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

        parsed: dict[str, object] | None = None
        stdout_lines = completed.stdout.strip().splitlines()
        if stdout_lines:
            try:
                parsed_value = json.loads(stdout_lines[-1])
                if isinstance(parsed_value, dict):
                    parsed = parsed_value
            except json.JSONDecodeError:
                parsed = None

        if parsed is None or completed.returncode == 125:
            record = _trial_record(
                trial_id=trial_id,
                tool=tool_name,
                agent_env=agent_env,
                policy=policy,
                op=op,
                path=path,
                status="infra_error",
                elapsed_ms=elapsed_ms,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                write_content=content if op == "write" else "",
            )
            _append_trial(trial_log, record)
            return "ERROR: worker did not return valid JSON"

    except subprocess.TimeoutExpired as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        record = _trial_record(
            trial_id=trial_id,
            tool=tool_name,
            agent_env=agent_env,
            policy=policy,
            op=op,
            path=path,
            status="infra_error",
            elapsed_ms=elapsed_ms,
            exit_code=None,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "",
            write_content=content if op == "write" else "",
        )
        _append_trial(trial_log, record)
        return "ERROR: worker timed out"

    except (OSError, KeyError) as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        record = _trial_record(
            trial_id=trial_id,
            tool=tool_name,
            agent_env=agent_env,
            policy=policy,
            op=op,
            path=path,
            status="infra_error",
            elapsed_ms=elapsed_ms,
            exit_code=None,
            stdout="",
            stderr=str(exc),
            write_content=content if op == "write" else "",
        )
        _append_trial(trial_log, record)
        return "ERROR: unable to start worker"

    worker_exit_code = parsed.get("exit_code")
    status = "success" if parsed.get("ok") is True else "worker_error"
    error = parsed.get("error")

    if isinstance(worker_exit_code, int):
        if worker_exit_code == 2:
            status = "policy_block"
        elif worker_exit_code == 3:
            status = "sandbox_block"
        elif worker_exit_code == 4:
            status = "not_found"

    record = _trial_record(
        trial_id=trial_id,
        tool=tool_name,
        agent_env=agent_env,
        policy=policy,
        op=op,
        path=path,
        status=status,
        elapsed_ms=elapsed_ms,
        exit_code=completed.returncode,
        worker_exit_code=worker_exit_code,
        worker_response=parsed,
        stdout=completed.stdout,
        stderr=completed.stderr,
        write_content=content if op == "write" else "",
    )
    _append_trial(trial_log, record)

    if parsed.get("ok") is True:
        if op == "read":
            return str(parsed.get("content", ""))
        return f"Write succeeded: {parsed.get('path', path)}"

    message = str(error) if error is not None else "worker request failed"
    return f"ERROR (exit {worker_exit_code if isinstance(worker_exit_code, int) else 1}): {message}"


def read_document(path: str) -> str:
    """Read a text file from the documents folder."""
    return run_worker("read", path, tool="read_document")


def write_output(path: str, content: str = "") -> str:
    """Save text to a file in the output folder."""
    return run_worker("write", path, content, tool="write_output")


@tool("read_document")
def read_document_tool(path: str) -> str:
    """Read a text file from the documents folder."""
    return read_document(path)


@tool("write_output")
def write_output_tool(path: str, content: str = "") -> str:
    """Save text to a file in the output folder."""
    return write_output(path, content)
