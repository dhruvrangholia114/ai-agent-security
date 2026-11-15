#!/usr/bin/env bash
set -euo pipefail

docker run --rm \
  --network none \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only \
  --pids-limit 64 \
  --memory 512m \
  --cpus 1 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  agent-security-test "$@"
