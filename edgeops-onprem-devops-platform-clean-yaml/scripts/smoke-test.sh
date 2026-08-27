#!/usr/bin/env bash
set -euo pipefail
API="${API:-http://localhost:8000}"
curl -fsS "$API/health" >/dev/null
curl -fsS "$API/ready" >/dev/null
curl -fsS "$API/api/summary" >/dev/null
echo "EdgeOps smoke test passed."
