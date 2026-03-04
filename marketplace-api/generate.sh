#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$ROOT/app/generated/openapi_server"
rm -rf "$ROOT/app/generated"
mkdir -p "$OUT_DIR"

if command -v openapi-generator-cli &>/dev/null; then
  GEN_TMP="$(mktemp -d)"
  openapi-generator-cli generate \
    -i "$ROOT/openapi/openapi.yaml" \
    -o "$GEN_TMP" \
    -g python-fastapi \
    --skip-validate-spec \
    --additional-properties=packageName=openapi_server,projectName=marketplace-api
  cp -r "$GEN_TMP/src/openapi_server/." "$OUT_DIR/"
  rm -rf "$GEN_TMP"
else
  CONTAINER_NAME="openapi-gen-$$"
  docker run --name "$CONTAINER_NAME" \
    -v "$ROOT/openapi:/openapi:ro" \
    openapitools/openapi-generator-cli generate \
    -i /openapi/openapi.yaml \
    -o /tmp/generated \
    -g python-fastapi \
    --additional-properties=packageName=openapi_server,projectName=marketplace-api
  docker cp "$CONTAINER_NAME:/tmp/generated/src/openapi_server/." "$OUT_DIR/"
  docker rm "$CONTAINER_NAME" >/dev/null
fi

echo "Файлы сгенерированы в: $OUT_DIR"
ls -la "$OUT_DIR"
