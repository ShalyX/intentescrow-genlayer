#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -d .venv312 ]; then
  # shellcheck disable=SC1091
  source .venv312/bin/activate
fi

pytest tests -q
genvm-lint lint contracts/intent_escrow.py --json
genvm-lint validate contracts/intent_escrow.py --json
genvm-lint check contracts/intent_escrow.py --json
