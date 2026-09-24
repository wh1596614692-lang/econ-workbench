FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN npm install --global pnpm@10.11.0 && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
COPY requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY econworkbench/ ./econworkbench/
COPY examples/ ./examples/
COPY docs/ ./docs/
COPY requirements.txt LICENSE THIRD_PARTY.md ./
COPY --from=frontend /build/dist ./frontend/dist/
RUN useradd --uid 10001 --create-home researcher
USER researcher
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/api/health')"
CMD ["python", "-m", "econworkbench.serve"]
