# ==============================================================================
# Workstation Manager - Production All-in-One Multi-Stage Dockerfile
# ==============================================================================

# ----------------------------------------------------
# Stage 1: Build Frontend (React + TypeScript + Vite)
# ----------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci

# Copy frontend source code and build production bundle
COPY . .
RUN npm run build

# ----------------------------------------------------
# Stage 2: Production Python Backend + Static Web App
# ----------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (tzdata for exact local time, wakeonlan, ping, curl, sqlite3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    wakeonlan \
    curl \
    iputils-ping \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone


# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy built frontend assets from Stage 1 into /app/dist
COPY --from=frontend-builder /app/dist /app/dist

# Copy application source code
COPY backend /app/backend
COPY agent /app/agent
COPY data /app/data
COPY scripts /app/scripts
RUN chmod +x /app/scripts/*.sh /app/scripts/*.py 2>/dev/null || true

# Ensure data directory exists for persistent storage
RUN mkdir -p /app/data

# Environment variable for port
ENV PORT=2301

# Expose web & API port
EXPOSE 2301

# Run FastAPI production server with proxy headers enabled
CMD ["sh", "-c", "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-2301} --proxy-headers --forwarded-allow-ips='*'"]
