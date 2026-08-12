#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NAME="${GITHUB_REPO_NAME:-SentinelAI}"
VIS="${GITHUB_VISIBILITY:-public}"

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login"
  exit 1
fi

if [[ -z "$(git rev-parse --verify HEAD 2>/dev/null || true)" ]]; then
  git add -A
  git commit -m "$(cat <<'EOF'
Initial SentinelAI platform: gateway, routing, guardrails, eval, copilot

EOF
)"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$NAME" --"$VIS" --source=. --remote=origin --push
else
  git push -u origin HEAD
fi

gh repo view --web || true
gh repo view --json url -q .url
