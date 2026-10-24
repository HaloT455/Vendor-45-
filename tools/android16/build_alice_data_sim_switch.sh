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
  if [[ -z "${R8_JAR:-}" || ! -s "$R8_JAR" ]]; then
    echo "ERROR: Android SDK d8 unavailable and R8_JAR not supplied" >&2
    echo "Download com.android.tools:r8 from Google's Maven repository, then:" >&2
    echo 'R8_JAR=/full/path/to/r8.jar bash tools/android16/build_alice_data_sim_switch.sh "$PWD/alice-data-sim-switch.jar"' >&2
    exit 2
  fi
  if ! jar tf "$R8_JAR" | grep -q '^com/android/tools/r8/D8.class
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/classes" "$TMP/dex" "$(dirname "$OUTPUT")"
javac --release 8 -d "$TMP/classes" "$SOURCE"
if [[ -n "$D8" ]]; then
  "$D8" --min-api 26 --output "$TMP/dex" "$TMP/classes/AliceDataSimSwitch.class"
else
  java -cp "$R8_JAR" com.android.tools.r8.D8 \
    --min-api 26 --output "$TMP/dex" "$TMP/classes/AliceDataSimSwitch.class"
fi
test -s "$TMP/dex/classes.dex"
(cd "$TMP/dex" && jar cf "$OUTPUT" classes.dex)
test -s "$OUTPUT"
echo "PASS: generated local Android DEX helper (NOT installed): $OUTPUT"
sha256sum "$OUTPUT"
; then
    echo "ERROR: R8_JAR does not contain Google's D8 entrypoint" >&2
    exit 2
  fi
  D8=""
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
