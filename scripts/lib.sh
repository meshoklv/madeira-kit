#!/bin/bash
# Shared helpers. Source me: . "$(dirname "$0")/lib.sh"
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CFG_FILE="${MADEIRA_KIT_CONFIG:-$KIT/scripts/config.env}"
[ -f "$CFG_FILE" ] || { echo "error: $CFG_FILE not found. Copy scripts/config.example.env to scripts/config.env and fill it in." >&2; exit 1; }
set -a; . "$CFG_FILE"; set +a
die() { echo "error: $*" >&2; exit 1; }
need() { [ -n "${!1:-}" ] || die "$1 is not set in $CFG_FILE"; }
[ "$(uname)" = "Darwin" ] || die "these scripts run on macOS (codesign, devicectl)"
APP="$WORK_DIR/Payload/Madeira.app"
