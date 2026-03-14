#!/usr/bin/env bash
# -------------------------------------------------------------------
# verify.sh — prove the live server runs the published source code
#
# Usage:
#   ./verify.sh https://qr.joinwebzero.com
#   ./verify.sh https://qr.joinwebzero.com --image  (also verify Docker image)
#
# Requirements: curl, sha256sum (or shasum on macOS), jq
# Optional:     cosign  (https://docs.sigstore.dev/cosign/installation)
# -------------------------------------------------------------------
set -euo pipefail

BASE_URL="${1:-}"
if [[ -z "$BASE_URL" ]]; then
  echo "Usage: $0 <server-url> [--image]"
  exit 1
fi
BASE_URL="${BASE_URL%/}"
CHECK_IMAGE="${2:-}"

echo ""
echo "=== Step 1: Fetch integrity info from live server ==="
INTEGRITY=$(curl -sf "${BASE_URL}/integrity")
echo "$INTEGRITY" | jq .

SERVER_HASH=$(echo "$INTEGRITY" | jq -r '.server_py_sha256')
GIT_SHA=$(echo    "$INTEGRITY" | jq -r '.git_commit')
RAW_URL=$(echo    "$INTEGRITY" | jq -r '.raw_url')

echo ""
echo "=== Step 2: Hash the published source at GitHub (commit ${GIT_SHA:0:8}) ==="
GITHUB_HASH=$(curl -sf "$RAW_URL" | sha256sum | awk '{print $1}')
echo "GitHub sha256 : $GITHUB_HASH"
echo "Server sha256 : $SERVER_HASH"

echo ""
if [[ "$SERVER_HASH" == "$GITHUB_HASH" ]]; then
  echo "✓  MATCH — the live server.py is identical to the published source."
else
  echo "✗  MISMATCH — the running code does NOT match the GitHub source!"
  exit 1
fi

echo ""
echo "=== Step 3: Verify redirect destinations are official app store URLs ==="
curl -sf "${BASE_URL}/destinations" | jq .

echo ""
if [[ "$CHECK_IMAGE" == "--image" ]]; then
  echo "=== Step 4: Verify Docker image signature in Rekor transparency log ==="
  if ! command -v cosign &>/dev/null; then
    echo "cosign not installed. Install from: https://docs.sigstore.dev/cosign/installation"
    exit 1
  fi
  IMAGE=$(echo "$INTEGRITY" | jq -r '.verify_image_command' | grep -oP "ghcr\.io/\S+")
  REPO_PATTERN=$(echo "$INTEGRITY" | jq -r '.source_url' | grep -oP "https://github.com/[^/]+/[^/]+")
  cosign verify \
    --certificate-identity-regexp="${REPO_PATTERN}/.*" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    "$IMAGE" | jq .
  echo ""
  echo "✓  Image signature verified in Rekor. Built by GitHub Actions from the published repo."
fi

echo ""
echo "Done. No trust required — you verified it yourself."
