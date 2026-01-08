# Build stage
FROM node:22-alpine AS build

WORKDIR /app

# Copy package files first (better layer caching)
COPY package*.json ./

# Install ALL dependencies for build
RUN npm ci --no-audit --no-fund && npm cache clean --force

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Dependencies stage - install production deps separately
FROM node:22-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund && \
    npm cache clean --force && \
    rm -rf /root/.npm /tmp/* && \
    # Remove unnecessary files from node_modules
    find /app/node_modules -name "*.md" -delete && \
    find /app/node_modules -name "*.ts" -not -name "*.d.ts" -delete && \
    find /app/node_modules -name "LICENSE*" -delete && \
    find /app/node_modules -name "CHANGELOG*" -delete && \
    find /app/node_modules -name ".npmignore" -delete && \
    find /app/node_modules -name ".eslintrc*" -delete && \
    find /app/node_modules -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/node_modules -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/node_modules -type d -name "__tests__" -exec rm -rf {} + 2>/dev/null || true

# Production stage - minimal runtime
FROM node:22-alpine AS runtime

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init && \
    addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs

WORKDIR /app

# Copy cleaned node_modules from deps stage
COPY --from=deps --chown=nodejs:nodejs /app/node_modules ./node_modules
COPY --from=deps --chown=nodejs:nodejs /app/package*.json ./

# Copy built assets only
COPY --from=build --chown=nodejs:nodejs /app/dist ./dist

# Set environment variables
ENV HOST=0.0.0.0 \
    PORT=4321 \
    NODE_ENV=production

# Switch to non-root user
USER nodejs

# Expose the port
EXPOSE 4321

# Use dumb-init for proper PID 1 handling
CMD ["dumb-init", "node", "./dist/server/entry.mjs"]
