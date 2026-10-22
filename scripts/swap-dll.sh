#!/bin/bash
# Replace one PE DLL inside the unpacked app (e.g. a patched d3d11.dll / ntdll.dll / xtajit64.dll
# built from patches/), before signing.
#   swap-dll.sh <your.dll> <name-in-app.dll> [expected-sha1]
set -euo pipefail
. "$(dirname "$0")/lib.sh"
SRC="${1:?usage: swap-dll.sh <dll> <target-name> [sha1]}"; NAME="${2:?target name, e.g. xtajit64.dll}"; WANT="${3:-}"
T="$APP/arm64ec-windows/$NAME"
[ -f "$T" ] || die "$T does not exist (run unpack.sh first; check the name)"
echo "was:  $(shasum "$T" | cut -d' ' -f1)"
cp "$SRC" "$T"
GOT=$(shasum "$T" | cut -d' ' -f1); echo "now:  $GOT"
[ -z "$WANT" ] || [ "$GOT" = "$WANT" ] || die "sha1 mismatch (expected $WANT)"
echo "swap ok - now run sign.sh"
