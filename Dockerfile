# syntax=docker/dockerfile:1

# Multi-stage build for smaller final image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1
# Copy from cache instead of linking (required for multi-stage)
ENV UV_LINK_MODE=copy

# Install dependencies first (better layer caching)
COPY uv.lock pyproject.toml ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code and install project
COPY src/ ./src/
COPY pages/ ./pages/
COPY main.py README.md ./
RUN uv sync --frozen --no-dev


# Final minimal image
FROM python:3.11-slim-bookworm

# Install curl for platform healthchecks
RUN apt-get update \ 
    && apt-get install -y --no-install-recommends curl \ 
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --system --gid 1000 app \
    && useradd --system --gid 1000 --uid 1000 --create-home app

WORKDIR /app

# Copy only the virtual environment and app from builder
COPY --from=builder --chown=app:app /app /app

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Streamlit configuration
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_THEME_BASE=dark

# Expose port
EXPOSE 8501

# Run as non-root user
USER app

# Run Streamlit directly (no uv needed at runtime)
CMD ["streamlit", "run", "main.py"]
