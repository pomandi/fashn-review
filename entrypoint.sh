#!/bin/sh
set -e

# Seed persistent data dir on first start (volume is empty)
if [ -d /app/data_seed ]; then
  mkdir -p /app/data
  # Copy each subfolder only if missing
  for sub in generations prompts feedback; do
    if [ -d "/app/data_seed/$sub" ] && [ ! -d "/app/data/$sub" ]; then
      cp -r "/app/data_seed/$sub" "/app/data/$sub"
    fi
  done
  # Top-level files
  for f in /app/data_seed/*.json; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    [ -e "/app/data/$name" ] || cp "$f" "/app/data/$name"
  done
fi

exec gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  wsgi:app
