# Run the Security Experiment on Linux (WSL/Ubuntu)

## What this is

This project runs one CrewAI agent through standard Docker, hardened Docker, and gVisor. The scripts perform 105 trials and save the tool calls and summary results under `results/`.

## Before you start

Use WSL Ubuntu with these requirements already available:

- Rootless Docker is installed and running.
- The `runsc` runtime is registered with Docker.
- You have your own OpenAI API key. Never use Ethan’s key or share your key in chat.
- Git has been configured with permission to push this repository.

## Quick environment check

Before cloning, verify Docker is using rootless mode:

```bash
docker context show
```

It should print `rootless`. If it prints anything else, stop and fix the Docker setup before continuing.

Clone the repository and enter it:

```bash
git clone https://github.com/ethanlongney/ai-agent-security.git
cd ai-agent-security
```

Save the Linux environment details as evidence:

```bash
mkdir -p results
{
  date
  uname -a
  python3 --version
  docker version --format '{{.Server.Version}}'
  runsc --version
  docker info --format '{{json .SecurityOptions}}'
} > results/linux_env.txt 2>&1

cat results/linux_env.txt
docker context show
```

## Setup

From the project repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `python3 -m venv` fails, install the Ubuntu venv package and try again:

```bash
sudo apt install python3-venv
python3 -m venv .venv
```

On a system using a specific Python 3.13 package, use `python3.13-venv` instead if `python3-venv` is unavailable.

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=your-own-openai-key
MODEL_NAME=openai/gpt-4o-mini
CREWAI_DISABLE_TELEMETRY=true
CREWAI_TRACING_ENABLED=false
OTEL_SDK_DISABLED=true
```

Do not put a real key in the instructions, this file, or git. `.env` must not be committed.

## Run the preflight

From the project root:

```bash
./experiments/preflight.sh 2>&1 | tee results/preflight_linux.txt
```

Send Ethan the **whole terminal output**, not a screenshot. Stop and do not continue if any check says `FAIL` or if the final line is `PREFLIGHT FAILED`.

## Run the batch

After a successful preflight:

```bash
./experiments/run_all.sh 2>&1 | tee results/run_all_linux.txt
```

The batch normally takes about 15–25 minutes for 105 runs. Keep the terminal open and prevent the PC from sleeping until it prints `Batch complete`.

## Send results back

When the batch finishes:

```bash
git add results/
git commit -m "Add Linux experiment results"
git push
```

Do not run `git add .env` or add `.env` to the commit.

## If something fails

- Do not rerun individual trials by hand.
- Do not delete logs, CSV files, or partial results.
- Send Ethan the complete terminal screen output and the relevant `results/` files.
