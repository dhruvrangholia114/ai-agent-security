#!/usr/bin/env bash
set -euo pipefail

docker run --rm -i --user 0 agent-security-test "$@"
