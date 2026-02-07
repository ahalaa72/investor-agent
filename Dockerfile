# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    gnupg2 \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Microsoft ODBC Driver 18 for SQL Server
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,armhf,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install all dependencies in one go for faster builds
RUN /root/.local/bin/uv pip install --system \
    alpaca-py \
    "finvizfinance>=0.14.0" \
    "fredapi>=0.5.0" \
    "hishel>=0.1.3" \
    "html5lib>=1.1" \
    "httpx>=0.28.1" \
    "lxml>=6.0.1" \
    "mcp[cli]>=1.14.1" \
    "pandas>=2.3.2" \
    "pytrends>=4.9.2" \
    "questrade-api>=1.0.0" \
    "requests-cache>=1.2.1" \
    "tenacity>=9.1.2" \
    "yfinance[nospam]>=0.2.66" \
    "numpy>=2.0.0" \
    "scipy>=1.14.0" \
    "scikit-learn>=1.3.0" \
    "statsmodels>=0.14.0" \
    "cryptography>=42.0.0" \
    "tradingview-screener>=1.0.0" \
    "sqlalchemy>=2.0.0" \
    "pyodbc>=5.0.0"

# Copy only the investor_agent package (the source code we need)
COPY investor_agent ./investor_agent

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Use entrypoint for token decryption
ENTRYPOINT ["/docker-entrypoint.sh"]

# Keep container running - Claude Desktop will exec into it
CMD ["tail", "-f", "/dev/null"]
