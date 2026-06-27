#!/usr/bin/env bash
#
# Start the ventilation dashboard locally on http://localhost:8099
# Creates a venv + installs deps on first run.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "📦 creating venv + installing deps…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r backend/requirements.txt
fi

if [ ! -f backend/.env ]; then
  echo "⚠️  backend/.env not found — copy backend/.env.example to backend/.env and set HA_TOKEN."
  exit 1
fi

echo "🚀 http://localhost:8099"
cd backend
exec ../.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8099 "$@"
