# =============================================================================
# 肯葳科技亚马逊自动运营系统 — Docker Build
# Python 3.11 + Node.js 20 + Playwright/Chromium
# Supports: Mac (Intel/Apple Silicon), Windows, Linux
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Python + Node.js base
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

# Install Node.js 20 + system deps for Playwright/Chromium + Chinese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    # Playwright/Chromium runtime dependencies
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    # Chinese font support (for Excel/PDF reports)
    fonts-noto-cjk \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser
RUN playwright install chromium \
    && playwright install-deps chromium 2>/dev/null || true

# ---------------------------------------------------------------------------
# Stage 2: Build the Next.js dashboard
# ---------------------------------------------------------------------------
FROM base AS dashboard-builder

WORKDIR /app/dashboard

COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci --production=false 2>/dev/null || npm install --production=false

COPY dashboard/ .

# Ensure directories exist for build
RUN mkdir -p /app/processed /app/dashboard/public

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3: Final production image
# ---------------------------------------------------------------------------
FROM base AS final

WORKDIR /app

# Copy Python scripts and project files
COPY scripts/ ./scripts/
COPY config.json ./config.json
COPY data_schemas.md* ./
COPY setup.sh* ./
COPY CLAUDE.md* ./

# Create directory structure
RUN mkdir -p inputs/sellersprite inputs/seller-central \
    processed outputs logs data \
    dashboard/app dashboard/public

# Copy built dashboard from builder stage
COPY --from=dashboard-builder /app/dashboard/package.json /app/dashboard/
COPY --from=dashboard-builder /app/dashboard/package-lock.json* /app/dashboard/
COPY --from=dashboard-builder /app/dashboard/node_modules/ /app/dashboard/node_modules/
COPY --from=dashboard-builder /app/dashboard/.next/ /app/dashboard/.next/
COPY --from=dashboard-builder /app/dashboard/app/ /app/dashboard/app/
COPY --from=dashboard-builder /app/dashboard/next.config.js* /app/dashboard/
COPY --from=dashboard-builder /app/dashboard/public/ /app/dashboard/public/

# Environment defaults
ENV NODE_ENV=production \
    PORT=3000 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

EXPOSE 3000

# Health check — verify dashboard is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -sf http://localhost:3000/api/status || exit 1

# Start the dashboard (production mode)
CMD ["sh", "-c", "cd /app/dashboard && npm start"]
