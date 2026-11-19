#!/usr/bin/env bash
set -uo pipefail

ENVS="${ENVS:-standard hardened gvisor}"
TRIALS="${TRIALS:-5}"
OUT="${OUT:-results}"

cd "$(dirname "$0")/.."
PROJECT_ROOT="$PWD"

if [[ ! -f ".env" ]]; then
  echo "Setup error: missing $PROJECT_ROOT/.env" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Setup error: docker is not installed or not on PATH" >&2
  exit 2
fi

if ! docker info >/dev/null 2>&1; then
  echo "Setup error: Docker daemon is unavailable" >&2
  exit 2
fi

for env_name in $ENVS; do
  case "$env_name" in
    standard|hardened|gvisor) ;;
    *) echo "Setup error: unknown environment '$env_name'" >&2; exit 2 ;;
  esac
done

if [[ " $ENVS " == *" gvisor "* ]] \
  && ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q 'runsc'; then
  echo "Setup error: gVisor runtime 'runsc' is unavailable" >&2
  exit 2
fi

if [[ ! "$TRIALS" =~ ^[1-9][0-9]*$ ]]; then
  echo "Setup error: TRIALS must be a positive integer" >&2
  exit 2
fi

if [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  echo "Setup error: python3 is unavailable" >&2
  exit 2
fi

if ! "$PYTHON" -c "import crewai" >/dev/null 2>&1; then
  echo "Setup error: CrewAI is not importable in $PYTHON" >&2
  exit 2
fi

if [[ "$OUT" = /* ]]; then
  OUT_DIR="$OUT"
else
  OUT_DIR="$PROJECT_ROOT/$OUT"
fi

if [[ -f "$OUT_DIR/trials.csv" ]]; then
  echo "Setup error: $OUT already has results; use a new OUT or move them" >&2
  exit 2
fi

mkdir -p "$OUT_DIR/logs" "$OUT_DIR/console"

echo "Building sandbox image..."
if ! docker build -f sandbox/Dockerfile -t agent-security-test "$PROJECT_ROOT"; then
  echo "Setup error: Docker image build failed" >&2
  exit 2
fi

warm_up() {
  local env_name="$1"
  local script

  case "$env_name" in
    standard) script="sandbox/standard/run-standard.sh" ;;
    hardened) script="sandbox/hardened/run-hardened.sh" ;;
    gvisor) script="sandbox/gvisor/run-gvisor-hardened.sh" ;;
  esac

  echo "Warming up $env_name sandbox..."
  if ! "$PROJECT_ROOT/$script" python agents/worker.py read report_clean.txt --policy on >/dev/null; then
    echo "Setup error: $env_name sandbox warm-up failed" >&2
    exit 2
  fi
}

for env_name in $ENVS; do
  warm_up "$env_name"
done

env_count=$(wc -w <<<"$ENVS" | tr -d ' ')
planned_count=$((TRIALS * 7 * env_count))
start_time=$(date)
start_epoch=$(date +%s)
run_number=0
success_count=0
failure_count=0

mkdir -p "$OUT_DIR/console"
echo "Starting batch: ENVS=[$ENVS] TRIALS=$TRIALS OUT=$OUT"
echo "Start time: $start_time"

run_trial() {
  local scenario="$1"
  local env_name="$2"
  local policy="$3"
  local trial="$4"
  local trial_name

  if [[ "$scenario" == "control" ]]; then
    local env_code
    case "$env_name" in
      standard) env_code="STD" ;;
      hardened) env_code="HARD" ;;
      gvisor) env_code="GV" ;;
    esac
    trial_name="CTRL-${env_code}-ON-$(printf '%02d' "$trial")"
  else
    local env_code
    case "$env_name" in
      standard) env_code="STD" ;;
      hardened) env_code="HARD" ;;
      gvisor) env_code="GV" ;;
    esac
    local policy_code
    policy_code=$(printf '%s' "$policy" | tr '[:lower:]' '[:upper:]')
    trial_name="${scenario}-${env_code}-${policy_code}-$(printf '%02d' "$trial")"
  fi

  run_number=$((run_number + 1))

  if "$PYTHON" -m experiments.run_trials \
    --scenario "$scenario" \
    --env "$env_name" \
    --policy "$policy" \
    --trial "$trial" \
    --out "$OUT" \
    > "$OUT_DIR/console/$trial_name.txt" 2>&1; then
    success_count=$((success_count + 1))
    echo "[$run_number/$planned_count] $scenario $env_name $policy #$trial ... ok"
  else
    failure_count=$((failure_count + 1))
    echo "[$run_number/$planned_count] $scenario $env_name $policy #$trial ... FAILED"
  fi
}

for trial in $(seq 1 "$TRIALS"); do
  for env_name in $ENVS; do
    run_trial control "$env_name" on "$trial"

    for scenario in A B C; do
      for policy in on off; do
        run_trial "$scenario" "$env_name" "$policy" "$trial"
      done
    done
  done
done

end_time=$(date)
end_epoch=$(date +%s)
if [[ -f "$OUT_DIR/trials.csv" ]]; then
  csv_rows=$(($(wc -l < "$OUT_DIR/trials.csv") - 1))
else
  csv_rows=0
fi

echo "Batch complete"
echo "Start time: $start_time"
echo "End time: $end_time"
echo "Succeeded / failed / planned: $success_count / $failure_count / $planned_count"
echo "CSV rows: $csv_rows"
