#!/usr/bin/env bash
# Off-device unit tests for NirixX core (pure-Java protocol classes).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
JAVA=${JAVA:-/home/user/venv/lib/python3.11/site-packages/jdk4py/java-runtime/bin/java}
ECJ=${ECJ:-/home/user/tooling/lib/ecj.jar}
OUT="$ROOT/tests/out"
rm -rf "$OUT"; mkdir -p "$OUT"
find "$ROOT/app/src/com/nirixx/app/core/uds" "$ROOT/app/src/com/nirixx/app/core/vin" -name '*.java' > "$OUT/sources.txt"
# pure-Java support classes (no android imports)
echo "$ROOT/app/src/com/nirixx/app/core/diag/TestAddr.java" >> "$OUT/sources.txt"
echo "$ROOT/app/src/com/nirixx/app/core/diag/BatteryAssess.java" >> "$OUT/sources.txt"
echo "$ROOT/tests/jvm/TestCore.java" >> "$OUT/sources.txt"
"$JAVA" -cp "$ECJ" org.eclipse.jdt.internal.compiler.batch.Main -1.8 -nowarn -proc:none -d "$OUT/classes" @"$OUT/sources.txt"
"$JAVA" -cp "$OUT/classes" TestCore
