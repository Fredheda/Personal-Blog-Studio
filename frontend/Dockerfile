# Studio image. Build context is frontend/: `docker build -t blogstudio-web .`
FROM node:24-alpine AS deps
WORKDIR /app
# npm 12 blocks dependency install scripts unless package.json's `allowScripts`
# allows them. Pinned exactly; it needs Node ^24.15.0 (the base image is newer).
RUN npm install -g npm@12.2.2 && npm --version
COPY package.json package-lock.json ./
RUN npm ci

FROM node:24-alpine AS builder
WORKDIR /app
RUN npm install -g npm@12.2.2 && npm --version
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:24-alpine AS runner
WORKDIR /app
# Every stage carries the pin (backend/tests/test_npm_pin.py); the runner
# never runs npm, so the pin only keeps the three stages uniform.
RUN npm install -g npm@12.2.2 && npm --version
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
