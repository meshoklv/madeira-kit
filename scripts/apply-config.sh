#!/bin/bash
# Put a madeira.cfg on the phone (USB), read it back to verify, prepare the Wine profile and rotate the old log.
#   apply-config.sh configs/ds1-play.cfg
set -euo pipefail
. "$(dirname "$0")/lib.sh"
CFG="${1:?usage: apply-config.sh <file.cfg>}"; [ -f "$CFG" ] || die "no such file: $CFG"
D="python3 $KIT/scripts/device.py"
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
$D put "$CFG" /Documents/madeira.cfg
$D get /Documents/madeira.cfg "$TMP" >/dev/null
cmp -s "$CFG" "$TMP" && echo "CFG VERIFIED" || die "madeira.cfg on the phone differs from $CFG"
$D profile fix
$D rotate /Documents/madeira-log.txt
cat <<MSG

Config applied. Now: fully close Madeira (swipe it away), enable JIT (e.g. StikDebug), start the game from Madeira.
Afterwards: scripts/pull-log.sh
MSG
