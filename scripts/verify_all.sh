#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
PYTEST_BIN="${PYTEST_BIN:-.venv/bin/pytest}"

echo "▶ [1/4] Running backend pytest..."
"$PYTEST_BIN" -q --tb=short

echo "▶ [2/4] Running pi-runtime build & tests..."
npm --prefix pi-runtime run build
npm --prefix pi-runtime test

echo "▶ [3/4] Running frontend lint, tests & production build..."
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build

echo "▶ [4/4] Running EvoCanvas convergence evaluation..."
"$PYTHON_BIN" scripts/run_convergence_eval.py

echo "✅ All EvoCanvas fullstack checks passed."
