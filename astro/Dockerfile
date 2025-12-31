# Build stage
FROM node:22-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including dev)
RUN npm ci

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Prune dev dependencies after build
RUN npm prune --omit=dev

# Production stage
FROM node:22-alpine AS runtime

WORKDIR /app

# Copy only what's needed for production
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./

# Set environment variables
ENV HOST=0.0.0.0
ENV PORT=4321
ENV NODE_ENV=production

# Expose the port
EXPOSE 4321

# Start the application
CMD ["node", "./dist/server/entry.mjs"]
