#!/usr/bin/env bash
# Deploy frontend to Vercel. Requires: vercel CLI logged in + VITE_API_BASE pointing at live API.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_BASE="${VITE_API_BASE:?Set VITE_API_BASE to your public API origin, e.g. https://sentinelai.fly.dev}"

cd "$ROOT/frontend"
npx --yes vercel@latest pull --yes --environment=production || true
npx --yes vercel@latest env add VITE_API_BASE production <<< "$API_BASE" || true
npx --yes vercel@latest build --prod || true
npx --yes vercel@latest deploy --prod --yes \
  --build-env VITE_API_BASE="$API_BASE" \
  --env VITE_API_BASE="$API_BASE"
