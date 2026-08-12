#!/usr/bin/env bash
# One-shot Fly.io deploy for SentinelAI (all-in-one API + UI)
set -euo pipefail
export PATH="${HOME}/.fly/bin:${PATH}"

APP_NAME="${FLY_APP_NAME:-sentinelai-satwik}"
REGION="${FLY_REGION:-iad}"

if ! fly auth whoami >/dev/null 2>&1; then
  echo "Not logged in. Run: fly auth login"
  exit 1
fi

fly apps list --json 2>/dev/null | grep -q "\"Name\": \"${APP_NAME}\"" \
  || fly apps list 2>/dev/null | grep -q "${APP_NAME}" \
  || fly apps create "${APP_NAME}"

# Volume for sqlite + chroma (ignore if exists)
fly volumes list -a "${APP_NAME}" | grep -q sentinelai_data \
  || fly volumes create sentinelai_data --region "${REGION}" --size 1 -a "${APP_NAME}" --yes

if [[ -n "${OPENAI_API_KEY:-}${ANTHROPIC_API_KEY:-}${GOOGLE_API_KEY:-}" ]]; then
  ARGS=()
  [[ -n "${OPENAI_API_KEY:-}" ]] && ARGS+=(OPENAI_API_KEY="${OPENAI_API_KEY}")
  [[ -n "${ANTHROPIC_API_KEY:-}" ]] && ARGS+=(ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}")
  [[ -n "${GOOGLE_API_KEY:-}" ]] && ARGS+=(GOOGLE_API_KEY="${GOOGLE_API_KEY}")
  fly secrets set -a "${APP_NAME}" "${ARGS[@]}"
fi

fly deploy -c fly.toml -a "${APP_NAME}"
echo "Deployed: https://${APP_NAME}.fly.dev"
