#!/bin/bash
# Install the signed app on the phone; app data (your game, configs) is kept.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
need DEVICE_ID; need BUNDLE_ID
codesign -v --strict "$APP" 2>&1 || die "app is not signed - run sign.sh first"
OUT=$(xcrun devicectl device install app --device "$DEVICE_ID" "$APP" 2>&1) || { echo "$OUT"; die "install failed (phone unlocked? trusted?)"; }
echo "$OUT" | grep -E "bundleID|rror" | head -5
echo "$OUT" | grep -q "bundleID: $BUNDLE_ID" && echo "INSTALL OK" || die "install did not report $BUNDLE_ID"
