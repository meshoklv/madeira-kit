#!/bin/bash
# Re-sign the unpacked Madeira.app with YOUR certificate and profile.
# Run from a logged-in macOS GUI session (keychain access). Identity, team and profile come from config.env.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
need BUNDLE_ID; need TEAM_ID; need SIGN_IDENTITY; need PROVISIONING_PROFILE
[ -d "$APP" ] || die "$APP not found (run unpack.sh first)"
[ -f "$PROVISIONING_PROFILE" ] || die "profile not found: $PROVISIONING_PROFILE"

/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $BUNDLE_ID" "$APP/Info.plist"
cp "$PROVISIONING_PROFILE" "$APP/embedded.mobileprovision"

ENTS="$WORK_DIR/ents.plist"; rm -f "$ENTS"; plutil -create xml1 "$ENTS"
for k in "application-identifier string $TEAM_ID.$BUNDLE_ID" \
         "com.apple.developer.team-identifier string $TEAM_ID" \
         "get-task-allow bool true" \
         "com.apple.developer.kernel.increased-memory-limit bool true" \
         "com.apple.developer.kernel.extended-virtual-addressing bool true"; do
  /usr/libexec/PlistBuddy -c "Add :$k" "$ENTS"
done

# The built-in JIT helper extension needs its own App ID; JIT is enabled externally (StikDebug), so drop it.
rm -rf "$APP/PlugIns"

# Sign inside-out: dylibs, frameworks, then the app itself.
find "$APP" -name "*.dylib" -type f -print0 | while IFS= read -r -d "" f; do
  codesign -f -s "$SIGN_IDENTITY" --timestamp=none "$f"
done
for f in "$APP"/Frameworks/*.framework; do
  [ -d "$f" ] && codesign -f -s "$SIGN_IDENTITY" --timestamp=none "$f"
done
codesign -f -s "$SIGN_IDENTITY" --timestamp=none --generate-entitlement-der --entitlements "$ENTS" "$APP"
codesign -v --strict "$APP" && echo "SIGN OK"
