#!/usr/bin/env bash
# Smoke-тест API приложения (этап 2). Запускать при работающем app_api_server.py
set -euo pipefail

BASE="${1:-http://localhost:8083}"

echo "== health =="
curl -sf "$BASE/health"
echo ""

echo "== guest =="
GUEST=$(curl -sf -X POST "$BASE/v1/auth/guest" -H 'Content-Type: application/json' -d '{}')
echo "$GUEST" | head -c 200
echo "..."
TOKEN=$(echo "$GUEST" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "== balance =="
curl -sf "$BASE/v1/me/balance" -H "Authorization: Bearer $TOKEN"
echo ""

echo "== tarot (может занять до 60с) =="
TAROT=$(curl -sf -X POST "$BASE/v1/divinations/tarot" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Тест API","selection":"manual","card_ids":["00-TheFool","16-TheTower","Cups01"]}')
echo "$TAROT" | python3 -c "import sys,json; d=json.load(sys.stdin); print('divination_id', d.get('divination_id'), 'free', d.get('balance',{}).get('free_divinations_remaining'))"

echo "== history =="
curl -sf "$BASE/v1/me/history" -H "Authorization: Bearer $TOKEN"
echo ""
echo "✅ API smoke OK"
