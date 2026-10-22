# Build context: apps/web      docker build -t dubforge-web apps/web
FROM node:22-alpine AS build

WORKDIR /app

# dependencies first -> cached until package-lock.json changes
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

COPY . .

# The browser calls the API on the same origin under /api (nginx proxies it), so the
# image needs no API address baked in and works on any host or port.
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- runtime: static files + reverse proxy, runs as a non-root user ----------------------
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD wget -q --spider http://127.0.0.1:8080/healthz || exit 1
