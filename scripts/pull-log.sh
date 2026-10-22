#!/bin/bash
# Pull the newest Madeira log from the phone (USB, phone unlocked) and analyse it.
#   pull-log.sh [label]
set -euo pipefail
. "$(dirname "$0")/lib.sh"
need LOG_DIR
LBL="${1:-run}"; mkdir -p "$LOG_DIR"
D="python3 $KIT/scripts/device.py"
NEWEST=$($D ls /Documents/logs 2>/dev/null | awk '/S_IFREG/{print $3}' | sort | tail -1 || true)
OUT="$LOG_DIR/$(date +%F_%H%M)-$LBL.txt"
if [ -n "$NEWEST" ]; then $D get "/Documents/logs/$NEWEST" "$OUT" >/dev/null
else $D get /Documents/madeira-log.txt "$OUT" >/dev/null 2>&1 || true; fi
[ -s "$OUT" ] || die "could not fetch a log (cable? phone unlocked?)"
echo "log: $OUT ($(du -h "$OUT" | cut -f1))"
python3 "$KIT/tools/analyze-log.py" "$OUT"
