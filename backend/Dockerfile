FROM python:3.12-slim

# Install system dependencies for WeasyPrint & C libraries on Debian
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-cffi \
    python3-brotli \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv installer
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency configs
COPY pyproject.toml uv.lock ./

# Install third-party python dependencies without attempting to build root project package yet
RUN uv sync --frozen --no-dev --no-install-project --no-cache

# Copy project source code (including src/ and app/)
COPY . .

# Complete sync to install project package
RUN uv sync --frozen --no-dev --no-cache

# Expose backend port
EXPOSE 8000

# Start FastAPI server via Uvicorn
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
