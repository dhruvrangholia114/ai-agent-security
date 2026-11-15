FROM python:3.13.8-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Install only the dependencies needed for the worker
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY agents/ ./agents/
COPY experiments/fixtures/ ./fixtures/

# Create a non-root user
RUN useradd --create-home --uid 10001 worker \
    && mkdir -p /workspace/output \
    && chown -R worker:worker /workspace

USER worker

CMD ["python", "--version"]
