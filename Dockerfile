# API/worker image and a separate UI target, installed offline from uv.lock wheels.
FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MIGRATIONS_DIR=/app/migrations
WORKDIR /app
COPY wheelhouse/backend /wheels
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir --no-index --find-links /wheels -r requirements.lock.txt \
 && pip install --no-cache-dir --no-index --find-links /wheels --no-deps notes-graphrag \
 && rm -rf /wheels
COPY migrations ./migrations
RUN useradd --uid 10001 --no-create-home app
USER 10001
EXPOSE 8000
ENTRYPOINT ["notes-graphrag"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]

FROM node:24-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm run build

FROM nginx:stable-alpine AS ui
COPY --from=frontend-build /build/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/templates/default.conf.template
EXPOSE 8501
