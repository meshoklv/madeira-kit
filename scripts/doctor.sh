#!/bin/bash
# Pre-flight: phone visible over USB, app installed, free space, your game copy present.
# Exit code = number of problems.
. "$(dirname "$0")/lib.sh"
need DEVICE_UDID; need DEVICE_ID; need BUNDLE_ID; need GAME_DIR
D="python3 $KIT/scripts/device.py"; BAD=0
ok()  { echo "ok:   $*"; }
bad() { echo "FAIL: $*"; BAD=$((BAD+1)); }

if pymobiledevice3 usbmux list 2>/dev/null | grep -q "$DEVICE_UDID"; then ok "phone visible over usbmux"
else bad "phone not found (cable? 'Trust this computer'?)"; fi

xcrun devicectl device info apps --device "$DEVICE_ID" 2>/dev/null | grep -qi "$BUNDLE_ID" \
  && ok "app $BUNDLE_ID installed" || bad "app not found on the phone (or phone locked)"

if I=$($D info 2>&1); then
  FREE=$(echo "$I" | sed -n 's/^FREE_GB=//p'); echo "      $(echo "$I" | head -1)"
  awk -v f="$FREE" 'BEGIN{exit !(f>=3)}' && ok "free space ${FREE} GB" || bad "low space: ${FREE} GB (want >= 3)"
  if [ -n "${GAME_EXE:-}" ]; then
    $D exists "$GAME_DIR/$GAME_EXE" && ok "game copy present ($GAME_DIR)" || bad "$GAME_DIR/$GAME_EXE not found"
  fi
  $D profile 2>&1 | grep -q "APPDATA=ok" && ok "Wine profile has AppData" || bad "Wine profile lacks AppData (apply-config.sh fixes it)"
else
  bad "AFC did not open: $(echo "$I" | tail -1)"
fi
[ $BAD = 0 ] && echo "RESULT: ready" || echo "RESULT: $BAD problem(s)"
exit $BAD
