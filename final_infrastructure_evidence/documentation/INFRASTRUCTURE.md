# AI Agent Security – Infrastructure Setup

## 1. Environment

Tested environment:
- Windows 11 with Ubuntu on WSL2
- Linux architecture: x86_64
- Docker Engine: 29.9.3
- Rootless Docker
- gVisor: release-20261109.0
- Python image: python:3.13.8-slim
- Container worker: UID 10001 (worker)

## 2. Project Structure

- sandbox/Dockerfile: Standard Docker image
- sandbox/hardened/run-hardened.sh: Hardened Docker execution
- sandbox/gvisor/run-gvisor-hardened.sh: Hardened Docker execution using gVisor
- docs/evidence/: Test evidence and outputs

## 3. Build the Docker Image

From the project root:

    docker build -t agent-security-test -f sandbox/Dockerfile .

## 4. Rootless Docker Verification

Check the active Docker context:

    docker context show

Expected context: rootless

Check Docker security options:

    docker info --format '{{json .SecurityOptions}}'

Expected security options include rootless.

## 5. Standard Docker Baseline

Run:

    docker run --rm agent-security-test

Expected output:

    Python 3.13.8

## 6. Hardened Docker Configuration

Run:

    ./sandbox/hardened/run-hardened.sh

The configuration applies:
- Network disabled
- All Linux capabilities dropped
- no-new-privileges enabled
- Read-only root filesystem
- PID limit: 64
- Memory limit: 512 MB
- CPU limit: 1
- Temporary filesystem: 64 MB, noexec, nosuid

## 7. gVisor Configuration

The rootless Docker daemon registers gVisor using:

    ~/.config/docker/daemon.json

Configuration:

    {
      "runtimes": {
        "runsc": {
          "path": "/usr/bin/runsc",
          "runtimeArgs": [
            "--ignore-cgroups"
          ]
        }
      }
    }

Restart the user Docker service after configuration changes:

    systemctl --user restart docker

Verify runtime registration:

    docker info --format '{{json .Runtimes}}'

## 8. Hardened gVisor Execution

Run:

    ./sandbox/gvisor/run-gvisor-hardened.sh

The script combines the hardened Docker restrictions with:

    --runtime=runsc

## 9. Verified Test Results

The following checks were completed successfully:

- Standard Docker container execution
- Rootless Docker container execution
- gVisor runtime execution
- Non-root worker identity (UID 10001)
- Network disabled in hardened container
- All capabilities dropped
- no-new-privileges enabled
- Read-only workspace
- Writable /tmp temporary filesystem

See:
- evidence/gvisor-test.txt
- evidence/gvisor-docker-test.txt

## 10. Important Notes

- The Docker daemon runs in rootless mode. The worker process also runs as a non-root user inside the container.
- These are separate security properties and should not be treated as equivalent.
- The --ignore-cgroups option is used for compatibility with the tested gVisor and WSL2 environment.
- The gVisor configuration and test results are specific to the environment documented above.
- Do not expose API keys inside the sandbox.
- Use synthetic test files and disposable containers only.
- Do not mount personal host directories or real credentials into test containers.
- The worker has no direct network access in the hardened configuration.
