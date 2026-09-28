#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:5000}"

echo "Running smoke test against $BASE_URL"
python3 scripts/smoke_test.py --base-url "$BASE_URL"
