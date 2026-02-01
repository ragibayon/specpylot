FROM python:3.12-slim

WORKDIR /app

# System deps for crosshair/solver
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src
COPY examples /app/examples

RUN pip install --no-cache-dir uv && \
    uv pip install --system .

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["specpylot"]
