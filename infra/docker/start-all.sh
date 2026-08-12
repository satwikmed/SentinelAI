#!/bin/sh
set -e
mkdir -p /data/chroma
cp /etc/nginx/sentinelai.conf /etc/nginx/conf.d/default.conf 2>/dev/null || true
nginx
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
