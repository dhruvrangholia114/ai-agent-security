FROM python:3.13.8-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Install only the dependencies needed for the worker


# Copy project code
COPY agents/ ./agents/
COPY experiments/fixtures/ ./fixtures/

# Create a non-root user
RUN useradd --create-home --uid 10001 worker \
    && mkdir -p /workspace/fixtures/output \
    && chown -R worker:worker /workspace \
    && chown -R root:root /workspace/fixtures/protected \
    && chmod 700 /workspace/fixtures/protected

USER worker

CMD ["python", "agents/worker.py"]
