#!/usr/bin/env bash
# Compile Android16 data subscription switching helper into DEX JAR.
# Only creates an artifact: NEVER runs ADB, flashes or changes SIM settings.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE="$ROOT/tools/android16/AliceDataSimSwitch.java"
OUTPUT="${1:-$ROOT/alice-data-sim-switch.jar}"
if ! command -v javac >/dev/null || ! command -v jar >/dev/null; then
  echo "ERROR: JDK with javac and jar required" >&2; exit 2
fi
D8="${D8_BIN:-}"
if [[ -z "$D8" ]] && command -v d8 >/dev/null; then
  D8="$(command -v d8)"
fi
if [[ -z "$D8" ]]; then
  for base in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}" "$HOME/Android/Sdk" /usr/lib/android-sdk; do
    [[ -d "$base/build-tools" ]] || continue
    while IFS= read -r candidate; do D8="$candidate"; done < <(
      find "$base/build-tools" -maxdepth 2 -type f -name d8 | sort -V)
    [[ -n "$D8" ]] && break
  done
fi
if [[ -z "$D8" || ! -x "$D8" ]]; then
  echo "ERROR: Android SDK Build-Tools d8 not found" >&2
  echo "Install Android SDK Build-Tools, then set D8_BIN=/full/path/to/d8" >&2
  exit 2
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/classes" "$TMP/dex" "$(dirname "$OUTPUT")"
javac --release 8 -d "$TMP/classes" "$SOURCE"
"$D8" --min-api 26 --output "$TMP/dex" "$TMP/classes/AliceDataSimSwitch.class"
test -s "$TMP/dex/classes.dex"
(cd "$TMP/dex" && jar cf "$OUTPUT" classes.dex)
test -s "$OUTPUT"
echo "PASS: generated local Android DEX helper (NOT installed): $OUTPUT"
sha256sum "$OUTPUT"
