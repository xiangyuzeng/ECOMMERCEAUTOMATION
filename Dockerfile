# =============================================================================
# ECOMMERCEAUTOMATION — Multi-stage Docker build
# Python 3.11 (data pipeline) + Node.js 20 (Next.js dashboard)
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Python base with Node.js
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

# Install Node.js 20, system deps for Playwright/Chromium, and general utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    # Playwright/Chromium dependencies
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
    fonts-noto-cjk \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and Chromium browser
RUN playwright install chromium \
    && playwright install-deps chromium 2>/dev/null || true

# ---------------------------------------------------------------------------
# Stage 2: Build the Next.js dashboard
# ---------------------------------------------------------------------------
FROM base AS dashboard-builder

WORKDIR /app/dashboard

COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm install --production=false

COPY dashboard/ .

# Copy processed data so next build can resolve static imports if needed
COPY processed/ /app/processed/

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3: Final production image
# ---------------------------------------------------------------------------
FROM base AS final

WORKDIR /app

# Copy the entire project source
COPY scripts/ ./scripts/
COPY config.json* ./
COPY data_schemas.md* ./
COPY setup.sh* ./
COPY CLAUDE.md* ./

# Create directory structure
RUN mkdir -p inputs/sellersprite inputs/seller-central inputs/product-costs \
    processed outputs logs data \
    dashboard/app dashboard/public

# Copy built dashboard from stage 2
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

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

CMD ["sh", "-c", "cd /app/dashboard && npm run dev"]
