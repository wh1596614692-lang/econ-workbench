#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
if [ ! -f .venv/.dependencies-ready ]; then
  .venv/bin/python -m pip install -r requirements-lock.txt
  touch .venv/.dependencies-ready
fi
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
exec .venv/bin/python -m uvicorn econworkbench.api:app --host 127.0.0.1 --port "${PORT:-8000}" --workers 1
