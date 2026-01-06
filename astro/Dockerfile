# Build stage
FROM node:22-alpine AS build

WORKDIR /app

# Copy package files first (better layer caching)
COPY package*.json ./

# Install dependencies with clean cache
RUN npm ci --no-audit --no-fund && npm cache clean --force

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Production stage - use distroless or slim runtime
FROM node:22-alpine AS runtime

# Install dumb-init for proper signal handling (smaller than tini)
RUN apk add --no-cache dumb-init && \
    addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 -G nodejs

WORKDIR /app

# Copy only production dependencies from a clean install
COPY package*.json ./
RUN npm ci --omit=dev --no-audit --no-fund && npm cache clean --force

# Copy built assets
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
