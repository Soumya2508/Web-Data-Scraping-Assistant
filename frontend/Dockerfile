FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json /app/
RUN npm ci
COPY . /app

# If provided at build time, Vite will inline it into the build.
ARG VITE_BACKEND_URL=
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL

RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Single-page app fallback
RUN printf 'server {\n  listen 80;\n  server_name _;\n  root /usr/share/nginx/html;\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
