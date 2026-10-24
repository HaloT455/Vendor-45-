#!/usr/bin/env bash
# Build Android16 app_process helper as DEX jar. No ADB/device changes.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JAVA_SOURCE="$ROOT/tools/android16/AliceDataSimSwitch.java"
OUTPUT="${1:-$ROOT/alice-data-sim-switch.jar}"
command -v javac >/dev/null || { echo "Missing javac (JDK)" >&2; exit 2; }
command -v jar >/dev/null || { echo "Missing jar (JDK)" >&2; exit 2; }
D8="${D8_BIN:-}"
if [[ -z "$D8" ]] && command -v d8 >/dev/null 2>&1; then D8="$(command -v d8)"; fi
if [[ -z "$D8" ]]; then
  for base in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}" "$HOME/Android/Sdk" /usr/lib/android-sdk; do
    [[ -d "$base/build-tools" ]] || continue
    while IFS= read -r candidate; do D8="$candidate"; done < <(find "$base/build-tools" -maxdepth 2 -type f -name d8 | sort -V)
    [[ -n "$D8" ]] && break
  done
fi
if [[ -n "$D8" && ! -x "$D8" ]]; then D8=""; fi
if [[ -z "$D8" ]]; then
  if [[ -z "${R8_JAR:-}" || ! -s "${R8_JAR:-}" ]]; then
    echo "Missing d8 and R8_JAR. Download com.android.tools:r8 from Google Maven" >&2
    echo "Set R8_JAR=/path/to/r8.jar and retry." >&2
    exit 2
  fi
  if ! jar tf "$R8_JAR" | grep "^com/android/tools/r8/D8.class$" >/dev/null; then
    echo "Invalid R8_JAR; missing com.android.tools.r8.D8 class" >&2
    exit 2
  fi
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/classes" "$TMP/dex" "$(dirname "$OUTPUT")"
javac --release 8 -d "$TMP/classes" "$JAVA_SOURCE"
if [[ -n "$D8" ]]; then
  "$D8" --min-api 26 --output "$TMP/dex" "$TMP/classes/AliceDataSimSwitch.class"
else
  java -cp "$R8_JAR" com.android.tools.r8.D8 --min-api 26 --output "$TMP/dex" "$TMP/classes/AliceDataSimSwitch.class"
fi
test -s "$TMP/dex/classes.dex"
( cd "$TMP/dex"; jar cf "$OUTPUT" classes.dex )
test -s "$OUTPUT"
echo "PASS: Android DEX jar built locally; no device changes: $OUTPUT"
sha256sum "$OUTPUT"
