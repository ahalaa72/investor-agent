# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install all dependencies in one go for faster builds
RUN /root/.local/bin/uv pip install --system \
    alpaca-py \
    "hishel>=0.1.3" \
    "html5lib>=1.1" \
    "httpx>=0.28.1" \
    "lxml>=6.0.1" \
    "mcp[cli]>=1.14.1" \
    "pandas>=2.3.2" \
    "pytrends>=4.9.2" \
    "requests-cache>=1.2.1" \
    "tenacity>=9.1.2" \
    "yfinance[nospam]>=0.2.66" \
    "numpy>=2.0.0" \
    "scipy>=1.14.0"

# Copy only the investor_agent package (the source code we need)
COPY investor_agent ./investor_agent

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Keep container running - Claude Desktop will exec into it
CMD ["tail", "-f", "/dev/null"]
