#!/usr/bin/env bash
# NirixX — hermetic build pipeline (no Gradle).
#
# Two environments are supported:
#   * CI  : ubuntu runner with ANDROID_HOME (build-tools) + JDK on PATH.
#   * dev : this sandbox (aapt2 + apksigner + JRE under /home/user/tooling).
#           No dexer is vendored locally, so the dex step must run in CI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VCODE=14
VNAME="1.6.3"

# ---------------------------------------------------------------- toolchain
detect() {
  if [ -n "${ANDROID_HOME:-}" ] && [ -d "$ANDROID_HOME/build-tools" ]; then
    BT="$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"
    AAPT2="$BT/aapt2"
    D8="$BT/d8"
    ZIPALIGN="$BT/zipalign"
    APKSIGNER_JAR="$BT/lib/apksigner.jar"
    ANDROID_JAR="$ANDROID_HOME/platforms/android-34/android.jar"
    JAVA_BIN="${JAVA_HOME:-/usr}/bin/java";  command -v java   >/dev/null && JAVA_BIN="$(command -v java)"
    KEYTOOL_BIN="${JAVA_HOME:-/usr}/bin/keytool"; command -v keytool >/dev/null && KEYTOOL_BIN="$(command -v keytool)"
    JAVAC="${JAVA_HOME:-/usr}/bin/javac";    command -v javac  >/dev/null && JAVAC="$(command -v javac)"
    COMPILER="javac"
  else
    TOOLS=/home/user/tooling
    AAPT2="$TOOLS/bin/aapt2"
    D8=""
    ZIPALIGN=""
    APKSIGNER_JAR="$TOOLS/lib/apksigner.jar"
    ANDROID_JAR=/home/user/android-sdk/platform/android.jar
    JAVA_BIN=/home/user/venv/lib/python3.11/site-packages/jdk4py/java-runtime/bin/java
    KEYTOOL_BIN="$(dirname "$JAVA_BIN")/keytool"
    JAVAC=""
    COMPILER="ecj"
    ECJ_JAR="$TOOLS/lib/ecj.jar"
    DX_JAR="$TOOLS/lib/dx.jar"
    [ -f "$DX_JAR" ] && D8="dx:$DX_JAR"
  fi
}
detect
echo "compiler=$COMPILER  aapt2=$(basename "$(dirname "$AAPT2")")/aapt2  dex=${D8:-none-local}"

KS="$ROOT/keystore/nirixx.jks"
KSPASS=android123

APP="$ROOT/app"
OUT="$ROOT/out"
rm -rf "$OUT"; mkdir -p "$OUT/compiled" "$OUT/gen" "$OUT/classes" "$OUT/dex"

# ---------------------------------------------------------------- resources
echo "== [1/6] aapt2 compile =="
"$AAPT2" compile --dir "$APP/res" -o "$OUT/compiled/res.zip"

echo "== [2/6] aapt2 link =="
"$AAPT2" link \
  -o "$OUT/app-unsigned.apk" \
  -I "$ANDROID_JAR" \
  --manifest "$ROOT/manifest/AndroidManifest.xml" \
  --java "$OUT/gen" \
  -A "$APP/assets" \
  --min-sdk-version 24 \
  --target-sdk-version 34 \
  --version-code "$VCODE" \
  --version-name "$VNAME" \
  "$OUT/compiled/res.zip"

# ---------------------------------------------------------------- java
echo "== [3/6] java compile ($COMPILER) =="
find "$OUT/gen" "$APP/src" -name "*.java" > "$OUT/sources.txt"
if [ "$COMPILER" = javac ]; then
  "$JAVAC" -source 7 -target 7 -nowarn -proc:none \
    -bootclasspath "$ANDROID_JAR" -classpath "$ANDROID_JAR" \
    -d "$OUT/classes" @"$OUT/sources.txt" 2> "$OUT/build.log" || { cat "$OUT/build.log"; exit 1; }
  grep -v "^warning:" "$OUT/build.log" | head -5 || true
else
  # ECJ keeps going after errors and simply DROPS the offending class files —
  # a previous build silently shipped without Ui.class because this output was
  # never checked.  Capture it and refuse to package on any ERROR.
  "$JAVA_BIN" -cp "$ECJ_JAR" org.eclipse.jdt.internal.compiler.batch.Main -1.7 -nowarn -proc:none \
    -bootclasspath "$ANDROID_JAR" -classpath "$ANDROID_JAR" \
    -d "$OUT/classes" @"$OUT/sources.txt" > "$OUT/build.log" 2>&1 || true
  if grep -q "ERROR" "$OUT/build.log"; then
    cat "$OUT/build.log"
    echo "!! compile FAILED — ECJ dropped classes; refusing to package a broken dex"
    exit 1
  fi
fi
echo "   classes: $(find "$OUT/classes" -name '*.class' | wc -l)"
# belt-and-braces: classes that must always exist after a healthy compile
for K in com/nirixx/app/Ui.class com/nirixx/app/NirixXApp.class \
         com/nirixx/app/SplashActivity.class com/nirixx/app/HomeActivity.class \
         com/nirixx/app/R.class; do
  [ -f "$OUT/classes/$K" ] || { echo "!! missing $K after compile — aborting"; exit 1; }
done

# ---------------------------------------------------------------- dex
echo "== [4/6] dex =="
if [ "${D8#dx:}" != "$D8" ]; then
  # local sandbox: classic dx on the sandbox JRE
  (cd "$OUT/classes" && find . -name '*.class' -print0 | \
      xargs -0 "$JAVA_BIN" -jar "${D8#dx:}" --dex --no-strict --output="$OUT/dex/classes.dex")
elif [ -n "$D8" ] && [ -x "$D8" ]; then
  (cd "$OUT/classes" && find . -name '*.class' -print0 | xargs -0 "$D8" \
      --min-api 24 --output "$OUT/dex" --lib "$ANDROID_JAR")
else
  echo "!! no d8/dx available in this environment — dex step runs in CI."
  echo "   (artifact so far: $OUT/app-unsigned.apk, resources + manifest only)"
  exit 0
fi

echo "== [5/6] package dex =="
python3 - "$OUT/app-unsigned.apk" "$OUT/dex/classes.dex" <<'PY'
import zipfile, sys, shutil
apk, dex = sys.argv[1], sys.argv[2]
tmp = apk + ".tmp"
with zipfile.ZipFile(apk) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        zout.writestr(item, zin.read(item.filename))
    zout.write(dex, "classes.dex")
shutil.move(tmp, apk)
print("   dex added")
PY

# ---------------------------------------------------------------- align + sign
if [ ! -f "$KS" ]; then
  echo "== generating dev keystore =="
  mkdir -p "$ROOT/keystore"
  "$KEYTOOL_BIN" -genkeypair -alias nirixx -keyalg RSA -keysize 2048 -validity 10950 \
    -keystore "$KS" -storepass "$KSPASS" -keypass "$KSPASS" \
    -dname "CN=NirixX, OU=Diagnostics, O=NirixX Labs, L=Chennai, ST=Tamil Nadu, C=IN" >/dev/null 2>&1
fi

echo "== [6/6] zipalign + sign =="
if [ -n "$ZIPALIGN" ] && [ -x "$ZIPALIGN" ]; then
  "$ZIPALIGN" -f 4 "$OUT/app-unsigned.apk" "$OUT/app-aligned.apk"
else
  python3 "$ROOT/tools/zipalign.py" "$OUT/app-unsigned.apk" "$OUT/app-aligned.apk"
fi
mv "$OUT/app-aligned.apk" "$OUT/app-unsigned.apk"

"$JAVA_BIN" -jar "$APKSIGNER_JAR" sign \
  --ks "$KS" --ks-pass pass:$KSPASS --key-pass pass:$KSPASS \
  --min-sdk-version 24 \
  --out "$ROOT/NirixX.apk" \
  "$OUT/app-unsigned.apk" 2>/dev/null

echo
echo "OK  Built: $ROOT/NirixX.apk ($(du -h "$ROOT/NirixX.apk" | cut -f1))  v$VNAME ($VCODE)"
