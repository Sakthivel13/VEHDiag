#!/usr/bin/env bash
# Bootstrap the offline NirixX build toolchain (sandbox / CI).
# Only GitHub (api/codeload/raw) + PyPI hosts are used. Safe to re-run.
set -e
ROOT=/home/user
TOOL=$ROOT/tooling
mkdir -p $TOOL/bin $TOOL/lib $ROOT/android-sdk/platform
RAW="Accept: application/vnd.github.raw"

echo "== [1/6] JRE (jdk4py wheel; keytool included, no javac needed) =="
if [ ! -x $ROOT/venv/bin/java ]; then
  python3 -m venv $ROOT/venv
  $ROOT/venv/bin/pip install -q jdk4py
fi
JRUN=$(ls -d $ROOT/venv/lib/python3*/site-packages/jdk4py/java-runtime | head -1)
export JAVA="$JRUN/bin/java"
$JAVA -version 2>&1 | head -1

echo "== [2/6] android.jar (API 34, Sable/android-platforms) =="
if [ ! -f $ROOT/android-sdk/platform/android.jar ]; then
  curl -sL -o /tmp/platforms.tgz https://codeload.github.com/Sable/android-platforms/tar.gz/refs/heads/master
  tar -xzf /tmp/platforms.tgz -C /tmp
  JAR=$(find /tmp -path '*android-34/android.jar' | head -1)
  cp "$JAR" $ROOT/android-sdk/platform/android.jar
fi
ls -la $ROOT/android-sdk/platform/android.jar

echo "== [3/6] aapt2 (Apktool 2.4.1 release asset) =="
if [ ! -x $TOOL/bin/aapt2 ]; then
  URL=$(curl -s https://api.github.com/repos/iBotPeaches/Apktool/releases/tags/v2.4.1 | \
        python3 -c "import sys,json;print([a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('.jar')][0])")
  curl -sL -o /tmp/apktool.jar "$URL"
  python3 - <<'EOF'
import zipfile, shutil, os, stat
z = zipfile.ZipFile('/tmp/apktool.jar')
src = z.read('prebuilt/linux/aapt2')
open('/home/user/tooling/bin/aapt2','wb').write(src)
os.chmod('/home/user/tooling/bin/aapt2', os.stat('/home/user/tooling/bin/aapt2').st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
print('aapt2 extracted')
EOF
fi
$TOOL/bin/aapt2 version

echo "== [4/6] ecj.jar (Eclipse ECJ 4.6.1, vendored in sneaxhuh/learning-go) =="
if [ ! -f $TOOL/lib/ecj.jar ]; then
  curl -sL -H "$RAW" -o $TOOL/lib/ecj.jar \
    "https://api.github.com/repos/sneaxhuh/learning-go/contents/pkg/mod/github.com/quay/claircore@v1.5.37/java/jar/testdata/manifest/ecj-4.6.1.jar"
fi
python3 -c "import zipfile; z=zipfile.ZipFile('$TOOL/lib/ecj.jar'); z.getinfo('org/eclipse/jdt/internal/compiler/batch/Main.class'); print('ecj jar OK:', len(z.namelist()), 'entries')"
$JAVA -jar $TOOL/lib/ecj.jar -version 2>&1 || true

echo "== [5/6] dx.jar (Buck minimal binaries, project-draco/data) =="
if [ ! -f $TOOL/lib/dx.jar ]; then
  curl -sL -H "$RAW" -o $TOOL/lib/dx.jar \
    "https://api.github.com/repos/project-draco/data/contents/binaries/minimal/buck/dx.jar"
fi
python3 -c "import zipfile; z=zipfile.ZipFile('$TOOL/lib/dx.jar'); names=z.namelist(); print('dx jar OK:', len(names), 'entries'); assert any(n.endswith('dx/command/Main.class') for n in names), 'dx Main missing'"

echo "== [6/6] apksigner jar (Sketchware-Pro app/libs) =="
if [ ! -f $TOOL/lib/apksigner.jar ]; then
  curl -sL -H "$RAW" -o $TOOL/lib/apksigner.jar \
    "https://api.github.com/repos/Sketchware-Pro/Sketchware-Pro/contents/app/libs/build-tools_apksigner_32.0.0.jar"
fi
python3 -c "import zipfile; z=zipfile.ZipFile('$TOOL/lib/apksigner.jar'); names=z.namelist(); print('apksigner jar OK:', len(names)); assert any('ApkSignerTool' in n for n in names)"
$JAVA -jar $TOOL/lib/apksigner.jar --version 2>/dev/null || $JAVA -cp $TOOL/lib/apksigner.jar com.android.apksigner.ApkSignerTool --version || true
echo "ALL TOOLS READY"
