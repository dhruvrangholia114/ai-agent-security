import os
import subprocess
import sys
from pathlib import Path

import pytest


WORKER = Path(__file__).resolve().parents[1] / "agents" / "worker.py"


@pytest.fixture
def workspace(tmp_path):
    documents = tmp_path / "documents"
    protected = tmp_path / "protected"
    output = tmp_path / "output"

    documents.mkdir()
    protected.mkdir()
    output.mkdir()

    (documents / "report_clean.txt").write_text("This is a benign report.", encoding="utf-8")
    (protected / "demo_secret.txt").write_text("SECRET_MARKER_7f3a", encoding="utf-8")
    os.symlink("../protected/demo_secret.txt", documents / "evil_link")

    return tmp_path


def run(ws, *args, stdin=""):
    environment = {
        **os.environ,
        "WORKER_READ_ROOT": str(ws / "documents"),
        "WORKER_WRITE_ROOT": str(ws / "output"),
    }
    return subprocess.run(
        [sys.executable, str(WORKER), *args],
        input=stdin,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_clean_read(workspace):
    result = run(workspace, "read", "report_clean.txt", "--policy", "on")
    assert result.returncode == 0
    assert "This is a benign report." in result.stdout


def test_escape_blocked(workspace):
    result = run(workspace, "read", "../protected/demo_secret.txt", "--policy", "on")
    assert result.returncode == 2
    assert "SECRET_MARKER_7f3a" not in result.stdout


def test_symlink_blocked(workspace):
    result = run(workspace, "read", "evil_link", "--policy", "on")
    assert result.returncode == 2


def test_missing_file_returns_4(workspace):
    result = run(workspace, "read", "nope.txt", "--policy", "on")
    assert result.returncode == 4


def test_valid_write(workspace):
    result = run(workspace, "write", "summary.txt", "--policy", "on", stdin="hello")
    assert result.returncode == 0
    assert (workspace / "output" / "summary.txt").read_text(encoding="utf-8") == "hello"


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permissions")
def test_os_denial(workspace):
    protected = workspace / "protected"
    try:
        os.chmod(protected, 0o000)
        result = run(workspace, "read", "../protected/demo_secret.txt", "--policy", "off")
        assert result.returncode == 3
        assert "SECRET_MARKER_7f3a" not in result.stdout
    finally:
        os.chmod(protected, 0o755)


def test_write_escape(workspace):
    result = run(workspace, "write", "../protected/pwned.txt", "--policy", "on", stdin="pwned")
    assert result.returncode == 2
    assert not (workspace / "protected" / "pwned.txt").exists()


def test_absolute_path(workspace):
    result = run(workspace, "read", "/etc/passwd", "--policy", "on")
    assert result.returncode == 2
