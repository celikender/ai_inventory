#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
exec uvicorn app.main:app --host 192.168.1.254 --port 8000 --reload
