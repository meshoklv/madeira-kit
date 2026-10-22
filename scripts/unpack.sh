#!/bin/bash
# Unpack a Madeira build (.zip from CI or a release) into a fresh work dir.
#   unpack.sh Madeira-build.zip
set -euo pipefail
. "$(dirname "$0")/lib.sh"
ZIP="${1:?usage: unpack.sh <Madeira.zip>}"
[ -f "$ZIP" ] || die "no such file: $ZIP"
need WORK_DIR
rm -rf "$WORK_DIR"; mkdir -p "$WORK_DIR/Payload"
ditto -x -k "$ZIP" "$WORK_DIR/Payload"
[ -d "$APP" ] || die "the zip does not contain Madeira.app at its top level"
echo "unpacked: $APP"
