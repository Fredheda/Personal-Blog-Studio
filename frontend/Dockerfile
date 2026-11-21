# Studio image. Build context is frontend/: `docker build -t blogstudio-web .`
FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS deps
WORKDIR /app
# npm 12 blocks dependency install scripts unless package.json's `allowScripts`
# allows them. Pinned exactly; it needs Node ^24.15.0 or >=26 (the base image is newer).
RUN npm install -g npm@12.2.2 && npm --version
COPY package.json package-lock.json ./
RUN npm ci

FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS builder
WORKDIR /app
RUN npm install -g npm@12.2.2 && npm --version
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS runner
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
