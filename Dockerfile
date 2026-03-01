# ============================================================
# STAGE 1: Builder — compile dependencies with build tools
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (only in this stage — won't ship to final image)
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install all Python dependencies
# FIX: cryptography>=46.0.5 resolves CVE-2026-26007 (Critical 8.2)
# FIX: pip upgraded to resolve CVE-2025-8869 and CVE-2026-1703
RUN pip install --upgrade pip && \
    /root/.local/bin/uv pip install --system \
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
    "cryptography>=46.0.5" \
    "tradingview-screener>=1.0.0" \
    "sqlalchemy>=2.0.0" \
    "pyodbc>=5.0.0"

# ============================================================
# STAGE 2: Runtime — minimal image, no build tools
# Eliminates: build-essential, binutils, gcc, git (removes ~30+ CVEs)
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# FIX: Upgrade all Debian packages to latest security patches
# Addresses fixable CVEs in gnutls, tar, and other system packages
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
    unixodbc \
    libkrb5-3 \
    libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

# Copy ODBC driver from builder
COPY --from=builder /opt/microsoft /opt/microsoft
COPY --from=builder /usr/lib/*/libmsodbcsql* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/lib/*/libodbc* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /etc/odbcinst.ini /etc/odbcinst.ini
COPY --from=builder /usr/share/keyrings/microsoft-prod.gpg /usr/share/keyrings/microsoft-prod.gpg

# Copy installed Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# FIX: Remove pip & setuptools from runtime — not needed at runtime
# Eliminates CVE-2025-8869 (Medium) & CVE-2026-1703 (Low)
RUN python -m pip install --upgrade pip && \
    python -m pip uninstall -y pip setuptools && \
    rm -rf /root/.cache/pip /tmp/*

# Copy application code
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
