FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG API_INTERNAL_URL=http://localhost:8000
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    API_INTERNAL_URL=${API_INTERNAL_URL}
RUN npm run build

FROM node:20-alpine AS runtime
RUN addgroup -g 1001 -S consultaion && adduser -S consultaion -u 1001 -G consultaion
WORKDIR /app
# outputFileTracingRoot points at the monorepo root. In this image the web app
# lives at /app relative to that root, so Next nests the runnable standalone
# bundle under `standalone/app`.
COPY --from=builder --chown=consultaion:consultaion /app/.next/standalone/app ./
COPY --from=builder --chown=consultaion:consultaion /app/.next/static ./.next/static
COPY --from=builder --chown=consultaion:consultaion /app/public ./public
USER consultaion
EXPOSE 3000
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:3000/api/healthz || exit 1
CMD ["node", "server.js"]
