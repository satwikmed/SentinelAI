#!/usr/bin/env bash
# Deploy / document Render free-tier cutover (no credit card).
set -euo pipefail
echo "1) Push main to GitHub"
echo "2) In Render: New → Blueprint → connect satwikmed/SentinelAI → apply render.yaml"
echo "3) Copy the service URL (https://sentinelai-api.onrender.com)"
echo "4) Update frontend/vercel.json rewrite destination to that URL"
echo "5) cd frontend && npx vercel --prod --yes"
