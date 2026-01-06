# =============================================================================
# Stage 1: Builder - Install dependencies
# =============================================================================
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies into a virtual environment
# Using --no-compile to skip bytecode generation (done at runtime if needed)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-compile -r requirements.txt && \
    # Clean up unnecessary files to reduce size
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete && \
    find /opt/venv -type f -name "*.pyo" -delete && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.md" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.rst" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.txt" ! -name "requirements.txt" -delete 2>/dev/null || true && \
    rm -rf /opt/venv/lib/python3.12/site-packages/pip && \
    rm -rf /opt/venv/lib/python3.12/site-packages/setuptools

# =============================================================================
# Stage 2: Runtime - Final lightweight image
# =============================================================================
FROM python:3.12-slim AS runtime

# Set environment variables for faster startup
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1 \
    PATH="/opt/venv/bin:$PATH"

# Create non-root user for security (combine commands to reduce layers)
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application code (combine into single layer)
COPY --chown=appuser:appgroup litellm_app.py prompts.yaml ./
COPY --chown=appuser:appgroup services/ ./services/
COPY --chown=appuser:appgroup storage/ ./storage/

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Health check (use curl if available, fallback to python)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run the application with optimized settings
CMD ["uvicorn", "litellm_app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
