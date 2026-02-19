# syntax=docker/dockerfile:1.6
ARG PYTHON_VERSION=3.13-alpine

# Builder stage: install dependencies with UV
FROM python:${PYTHON_VERSION} AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN --mount=type=cache,target=/var/cache/apk apk add \
    build-base \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

WORKDIR /app

# Install dependencies (cached when lockfile unchanged)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && \
    uv pip install -r <(uv export --no-dev --no-emit-project)

# Final runtime image
FROM python:${PYTHON_VERSION}
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy example source files
COPY *.py ./

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080
ENV PORT=8080

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --timeout-keep-alive 10"]
