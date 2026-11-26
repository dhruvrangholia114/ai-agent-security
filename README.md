# AI Agent Security Experiment

## Project overview

This project tests whether container isolation changes how a tool-using agent handles prompt injections and protected files. It compares standard Docker, hardened Docker, and hardened Docker running under gVisor. The policy switch separates worker-level path checks from OS or container containment.

The official experiment used 63 trials: three environments, three repetitions, and seven trial types per repetition. The trial types are one control and three injection scenarios run with both policy states. The official model was Ollama `qwen2.5:7b` at temperature 0.

## Software requirements

- WSL2 Ubuntu on Linux for the official run
- Python 3.13.18
- CrewAI 1.15.41
- Docker 29.9.3 with rootless Docker enabled
- gVisor runsc release-20261109.0
- Ollama with the `qwen2.5:7b` model
- Python package dependencies from `requirements.txt`
- pytest for worker unit tests

The container image is based on `python:3.13.8-slim`. The worker inside the container runs as UID 10001.

## Installation

From WSL2 Ubuntu:

```bash
cd ai-agent-security
git checkout main
git pull
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install and start rootless Docker, register the `runsc` runtime, and verify both installations:

```bash
docker context show
docker info --format '{{json .Runtimes}}'
```

The Docker context should report `rootless`, and the runtime list should include `runsc`. Rootless Docker setup, daemon configuration, and hardened container configuration are described in `docs/INFRASTRUCTURE.md`.

For an Ollama run, start Ollama and pull the model:

```bash
ollama pull qwen2.5:7b
ollama serve
```

Create `.env` in the project root. Do not commit real credentials. Example settings:

```dotenv
MODEL_NAME=ollama/qwen2.5:7b
OLLAMA_BASE_URL=http://127.0.0.1:11434
CREWAI_DISABLE_TELEMETRY=true
CREWAI_TRACING_ENABLED=false
OTEL_SDK_DISABLED=true
```

Restrict the file permissions:

```bash
chmod 600 .env
```

## Execution

Run the preflight checks before the experiment:

```bash
./experiments/preflight.sh 2>&1 | tee results/preflight_linux.txt
```

Do not continue if preflight reports `PREFLIGHT FAILED` or any `FAIL` result.

Run the batch:

```bash
./experiments/run_all.sh 2>&1 | tee results/run_all_linux.txt
```

The script creates one JSONL file per trial under `results/logs/`, console output under `results/console/`, and the summary at `results/trials.csv`. A successful batch ends with `BATCH COMPLETE`; an incomplete or failed batch ends with `BATCH INCOMPLETE` and exit code 1.

For a 63-trial official run:

```bash
ENVS="standard hardened gvisor" TRIALS=3 ./experiments/run_all.sh
```

Run the worker unit tests locally with:

```bash
python -m pytest -q tests/test_worker.py
```

## Submitted file structure

- `agents/`: CrewAI agent, tool definitions, and restricted worker
- `experiments/`: trial runner, batch runner, preflight script, and fixtures
- `sandbox/`: Docker image and standard, hardened, and gVisor launch scripts
- `tests/`: worker unit tests
- `docs/`: methodology and infrastructure documentation
- `final_infrastructure_evidence/`: official environment information, trial data, logs, console evidence, scripts, documentation, and manifest
- `RUN_ON_LINUX.md`: Linux setup and execution instructions
- `README.md`: project overview and reproduction guide

## Reused and contributed software

The project reused CrewAI, Docker, gVisor/runsc, Ollama, Qwen 2.5 7B, the development OpenAI connection, the Python slim image, and pytest. Dhruv contributed the rootless Docker and gVisor setup, original container scripts and Dockerfile, the official batch run, the Ollama connection change, and evidence packaging. Ethan contributed the worker, CrewAI tools and logging, agent builder, trial runner and classification, batch runner, preflight script, fixtures, unit tests, Linux instructions, and container-related modifications.
