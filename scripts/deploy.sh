#!/usr/bin/env bash
set -euo pipefail

NETWORK="${1:-studionet}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/contracts/intent_escrow.py"

cd "$ROOT"

if ! command -v genlayer >/dev/null 2>&1; then
  echo "genlayer CLI not found. Install it before deploying." >&2
  exit 1
fi

if [ -d .venv312 ]; then
  # shellcheck disable=SC1091
  source .venv312/bin/activate
fi

./scripts/check.sh

echo "Deploying IntentEscrow to GenLayer network: $NETWORK"
echo "Contract: $CONTRACT"

genlayer network set "$NETWORK"
genlayer deploy --contract "$CONTRACT"

echo "Deployment submitted. Inspect the tx receipt and trace; accepted/finalized alone is not enough."
