#!/usr/bin/env bash
set -euo pipefail

API="${API:-http://localhost:8000}"

echo "== EdgeOps business demo =="

echo "Creating a production cluster..."
CLUSTER=$(curl -fsS -X POST "$API/api/clusters" \
  -H 'Content-Type: application/json' \
  -d '{"name":"single-node-microk8s","environment":"production","location":"local-lab","kubernetes_version":"v1.34"}')

echo "$CLUSTER"

echo
echo "Sending healthy telemetry..."
curl -fsS -X POST "$API/api/telemetry" \
  -H 'Content-Type: application/json' \
  -d '{"cluster":"single-node-microk8s","cpu":45,"memory":61,"disk":72,"pods":30,"status":"healthy"}'

sleep 2

echo
echo "Sending critical storage telemetry..."
curl -fsS -X POST "$API/api/telemetry" \
  -H 'Content-Type: application/json' \
  -d '{"cluster":"single-node-microk8s","cpu":55,"memory":75,"disk":94,"pods":35,"status":"warning"}'

sleep 3

echo
echo "Summary:"
curl -fsS "$API/api/summary"

echo
echo
echo "Incidents:"
curl -fsS "$API/api/incidents"

echo
