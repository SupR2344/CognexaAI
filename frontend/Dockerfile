# ==============================================================================
# Cognexa AI Frontend - Multi-Stage Next.js Dockerfile
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Install Dependencies
# ------------------------------------------------------------------------------
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy dependency definition files
COPY package.json package-lock.json* ./

# Install clean dependencies
RUN npm ci || npm install

# ------------------------------------------------------------------------------
# Stage 2: Build Application
# ------------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next.js telemetry during build
ENV NEXT_TELEMETRY_DISABLED=1

# Pass public build-time environment variables
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL:-http://localhost:8000}

# Build Next.js application
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 3: Production Runner
# ------------------------------------------------------------------------------
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

# Create non-root user and group
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built application and runtime dependencies
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public

# Set file ownership to nextjs user
RUN chown -R nextjs:nodejs /app

USER nextjs

EXPOSE 3000

# Start Next.js production server
CMD ["npm", "start"]
