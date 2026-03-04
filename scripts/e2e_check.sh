#!/bin/sh
set -e
BASE="${1:-http://localhost:8000}"
API="$BASE/api/v1"

echo "=== Health ==="
curl -s "$BASE/health" | head -1

echo "=== Register USER ==="
REG=$(curl -s -X POST "$API/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"password123","role":"USER"}')
echo "$REG" | head -c 200
echo ""

echo "=== Register SELLER ==="
curl -s -X POST "$API/auth/register" -H "Content-Type: application/json" \
  -d '{"email":"seller@test.com","password":"password123","role":"SELLER"}' > /dev/null

echo "=== Login as SELLER ==="
TOKEN=$(curl -s -X POST "$API/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"seller@test.com","password":"password123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
[ -n "$TOKEN" ] && echo "Token received" || echo "Login failed"

echo "=== Create product (SELLER) ==="
PROD=$(curl -s -X POST "$API/products" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Test Product","description":"D","price":10.5,"stock":100,"category":"Electronics","status":"ACTIVE"}')
echo "$PROD" | head -c 200
echo ""

echo "=== Login as USER ==="
TOKEN_U=$(curl -s -X POST "$API/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"user@test.com","password":"password123"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
[ -n "$TOKEN_U" ] && echo "User token OK"

echo "=== List products ==="
curl -s "$API/products?page=0&size=5" -H "Authorization: Bearer $TOKEN_U" | head -c 300
echo ""

echo "=== Create order (USER) ==="
PID=$(echo "$PROD" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',1))" 2>/dev/null || echo "1")
ORDER=$(curl -s -X POST "$API/orders" -H "Authorization: Bearer $TOKEN_U" -H "Content-Type: application/json" \
  -d "{\"items\":[{\"product_id\":$PID,\"quantity\":2}]}")
echo "$ORDER" | head -c 300
echo ""

echo "=== Done ==="
