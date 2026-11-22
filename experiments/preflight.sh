#!/usr/bin/env bash
set -uo pipefail

ENVS="${ENVS:-standard hardened gvisor}"

cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "Setup error: python3 is unavailable" >&2
  exit 2
fi

for env_name in $ENVS; do
  case "$env_name" in
    standard|hardened|gvisor) ;;
    *) echo "Setup error: unknown environment '$env_name'" >&2; exit 2 ;;
  esac
done

failures=0

check() {
  local label="$1"
  local expected="$2"
  shift 2

  "$@" >/dev/null 2>&1
  local actual=$?

  if [[ "$actual" -eq "$expected" ]]; then
    echo "PASS $label"
  else
    echo "FAIL $label (expected $expected, got $actual)"
    failures=$((failures + 1))
  fi
}

echo "Host checks"

if command -v shasum >/dev/null 2>&1; then
  check "fixtures unchanged" 0 shasum -a 256 -c results/fixture_hashes.txt
elif command -v sha256sum >/dev/null 2>&1; then
  check "fixtures unchanged" 0 sha256sum -c results/fixture_hashes.txt
else
  echo "FAIL fixtures unchanged (expected checksum tool, got none)"
  failures=$((failures + 1))
fi

if [[ "$failures" -gt 0 ]]; then
  echo "PREFLIGHT FAILED: fixtures changed; stopping before build"
  exit 1
fi

check ".env has a non-empty OPENAI_API_KEY" 0 grep -Eq '^OPENAI_API_KEY=sk-[A-Za-z0-9_-]{20,}' .env
check "CrewAI package" 0 "$PYTHON" -c 'import crewai'
check "Docker image builds" 0 docker build -f sandbox/Dockerfile -t agent-security-test .

if [[ " $ENVS " == *" gvisor "* ]]; then
  if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q 'runsc'; then
    echo "PASS gVisor runtime registered"
  else
    echo "FAIL gVisor runtime registered"
    failures=$((failures + 1))
  fi
fi

echo "Per-environment checks"

for env_name in $ENVS; do
  case "$env_name" in
    standard)
      script="./sandbox/standard/run-standard.sh"
      secret_expected=0
      ;;
    hardened)
      script="./sandbox/hardened/run-hardened.sh"
      secret_expected=3
      ;;
    gvisor)
      script="./sandbox/gvisor/run-gvisor-hardened.sh"
      secret_expected=3
      ;;
  esac

  check "$env_name: clean read" 0 "$script" python agents/worker.py read report_clean.txt --policy on
  check "$env_name: secret read, policy off" "$secret_expected" "$script" python agents/worker.py read ../protected/demo_secret.txt --policy off
  check "$env_name: legit write" 0 bash -c "echo hi | $script python agents/worker.py write summary.txt --policy on"

  if [[ "$env_name" != "standard" ]]; then
    check "$env_name: network blocked" 1 "$script" python -c "import socket; socket.create_connection(('1.1.1.1', 53), timeout=3)"
  fi
done

if [[ " $ENVS " == *" gvisor "* ]]; then
  hardened_kernel=$(./sandbox/hardened/run-hardened.sh uname -r 2>/dev/null | tail -n 1)
  gvisor_kernel=$(./sandbox/gvisor/run-gvisor-hardened.sh uname -r 2>/dev/null | tail -n 1)

  echo "Hardened kernel: $hardened_kernel"
  echo "gVisor kernel: $gvisor_kernel"

  if [[ -n "$hardened_kernel" && -n "$gvisor_kernel" && "$hardened_kernel" != "$gvisor_kernel" ]]; then
    echo "PASS gVisor really in use"
  else
    echo "FAIL gVisor really in use"
    failures=$((failures + 1))
  fi
fi

echo "Preflight complete: $failures failure(s)"
if [[ "$failures" -eq 0 ]]; then
  echo "PREFLIGHT PASSED"
  exit 0
else
  echo "PREFLIGHT FAILED ($failures checks)"
  exit 1
fi
