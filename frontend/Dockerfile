# --- Etapa 1: compilar la SPA -------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

# Se instalan también las dependencias de desarrollo porque Vite, Tailwind y
# TypeScript viven ahí. `--include=dev` evita que un NODE_ENV=production
# heredado del entorno de build las omita.
COPY package.json package-lock.json ./
RUN npm ci --include=dev --no-audit --no-fund

COPY . .
RUN npm run build

# --- Etapa 2: servir con nginx ------------------------------------------------
FROM nginx:alpine

# Configuración propia: fallback SPA + proxy de /api y /ws al backend.
COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
