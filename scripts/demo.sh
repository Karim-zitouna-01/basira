#!/usr/bin/env bash
# Lance la démo : API Basira (port 8000) + interface (port 5173). Ctrl+C arrête les deux.
#   bash scripts/demo.sh                          # sans LLM (réponses de repli)
#   LLM_BASE_URL=http://192.168.137.222:8200/v1 bash scripts/demo.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"
export BASIRA_MODE="${BASIRA_MODE:-real}"

if [ -n "${LLM_BASE_URL:-}" ]; then
  echo "LLM : $LLM_BASE_URL"
  curl -s -m 5 "$LLM_BASE_URL/models" >/dev/null && echo "  joignable" || echo "  ⚠ injoignable : l'assistant utilisera les réponses de repli"
fi

uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 &
API=$!
trap 'kill $API 2>/dev/null' EXIT
until curl -s localhost:8000/api/sante >/dev/null; do sleep 1; done
echo "API prête : http://localhost:8000/docs"

cd web
[ -d node_modules ] || npm ci --no-audit --no-fund
npx vite --host 0.0.0.0 --port 5173
