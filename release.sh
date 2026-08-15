#!/bin/bash
# F1 25 AI Race Engineer — 一键发布脚本
# 用法: bash release.sh <新版本号，如 1.0.1>
# 前置：update.json 的 changelog 先编辑好；~/.android/f1-re-release.jks 签名已配置；
#       git 凭据（osxkeychain）可访问 GitHub；仓库已转公开（六镜像链依赖公开访问）。
# 流程：版本号替换 → 构建 release 签名 APK → 提交+tag+推送 → 创建 GitHub Release 上传 APK → purge jsDelivr

set -e
cd "$(dirname "$0")"

NEW_VER="$1"
if ! echo "$NEW_VER" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "用法: bash release.sh <版本号，如 1.0.1>"
  exit 1
fi

REPO="harries233/f1-race-engineer"
APK_NAME="F1-Race-Engineer.apk"

# 从 build.gradle.kts 读取当前版本
OLD_VER=$(grep -oE 'versionName = "[0-9.]+"' android/app/build.gradle.kts | grep -oE '[0-9.]+')

echo "========================================"
echo "  发布 v$NEW_VER (当前 v$OLD_VER)"
echo "========================================"

# 0. 前置检查：工作区必须干净（脚本会自己改版本号并提交）
if [ -n "$(git status --porcelain)" ]; then
  echo "✗ 工作区有未提交改动，请先提交或 stash"
  exit 1
fi

# 1. 替换版本号（幂等，old==new 时无变化）
python3 - "$OLD_VER" "$NEW_VER" <<'PY'
import re, sys
old, new = sys.argv[1], sys.argv[2]

def edit(path, fn):
    with open(path) as f: s = f.read()
    s2 = fn(s)
    if s2 != s:
        with open(path, 'w') as f: f.write(s2)
        print(f"  ✓ {path}")

def gradle(s):
    # 仅当版本号确实变化时才递增 versionCode（幂等：重复执行同版本不递增）
    if f'versionName = "{new}"' not in s:
        s = re.sub(r'versionCode = \d+', lambda m: f'versionCode = {int(m.group(0).split("=")[1].strip())+1}', s)
    s = re.sub(r'versionName = "[^"]*"', f'versionName = "{new}"', s)
    return s

edit('android/app/build.gradle.kts', gradle)
edit('update.json', lambda s: re.sub(r'"version":\s*"[^"]*"', f'"version": "{new}"', s).replace('v'+old, 'v'+new))
PY

# 2. 构建 release 签名 APK
echo "[2/6] 构建 release 签名 APK..."
bash build-apk.sh release

# 拷贝产物到仓库根（固定名，供 jsDelivr/raw 托管 + 提交）
APK_SRC=$(find android/app/build/outputs/apk/release -name '*.apk' ! -name '*unsigned*' | head -1)
if [ -z "$APK_SRC" ]; then
  echo "✗ 未找到 release APK"; exit 1
fi
cp "$APK_SRC" "$APK_NAME"
echo "  产物：$APK_NAME"

# 3. 校验产物版本号 + 签名
AAPT=$(find "$HOME/Library/Android/sdk/build-tools" -name aapt 2>/dev/null | sort -V | tail -1)
BADGING=$("$AAPT" dump badging "$APK_NAME" 2>/dev/null | head -1)
echo "  $BADGING"
if ! echo "$BADGING" | grep -q "versionName='$NEW_VER'"; then
  echo "✗ 构建产物版本号不匹配"; exit 1
fi
if ! echo "$BADGING" | grep -q "versionCode='$(grep -oE 'versionCode = [0-9]+' android/app/build.gradle.kts | grep -oE '[0-9]+')'"; then
  echo "✗ 构建产物 versionCode 不匹配"; exit 1
fi

# 4. 提交 + tag + 推送（github.com 偶发连接失败，带重试）
echo "[4/6] 提交并推送..."
push_retry() {
  for i in 1 2 3 4 5; do
    if "$@" 2>&1; then return 0; fi
    echo "  ⚠ 推送失败（网络抖动），重试 $i/5..."; sleep 5
  done
  echo "✗ 推送失败"; return 1
}
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -m "v$NEW_VER"
fi
if ! git tag -l "v$NEW_VER" | grep -q "v$NEW_VER"; then
  git tag "v$NEW_VER"
fi
push_retry git push
if ! git ls-remote --tags origin "v$NEW_VER" 2>/dev/null | grep -q "v$NEW_VER"; then
  push_retry git push origin "v$NEW_VER" || true
fi

# 5. 创建 GitHub Release + 上传 APK（钥匙串凭据）
echo "[5/6] 创建 GitHub Release..."
cred=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null)
GH_USER=$(echo "$cred" | sed -n 's/^username=//p')
GH_TOKEN=$(echo "$cred" | sed -n 's/^password=//p')
if [ -z "$GH_TOKEN" ]; then echo "✗ 无法获取 GitHub 凭据"; exit 1; fi
BODY=$(python3 -c "
import json
d = json.load(open('update.json'))
print(d.get('changelog', '') or 'v$NEW_VER')")
RELEASE_JSON=$(mktemp)
CODE=$(curl -s -o "$RELEASE_JSON" -w "%{http_code}" -u "$GH_USER:$GH_TOKEN" "https://api.github.com/repos/$REPO/releases/tags/v$NEW_VER")
if [ "$CODE" = "200" ]; then
  echo "  release 已存在，复用"
else
  # 注意：JSON 用 heredoc 生成，避免花括号被 bash 展开
  JSON_BODY=$(python3 - "$NEW_VER" "$BODY" <<'PY'
import json, sys
print(json.dumps({"tag_name": "v" + sys.argv[1],
                  "name": "F1 Race Engineer v" + sys.argv[1],
                  "body": sys.argv[2],
                  "draft": False,
                  "prerelease": False}))
PY
)
  curl -s -X POST -u "$GH_USER:$GH_TOKEN" -H "Accept: application/vnd.github+json" \
    -d "$JSON_BODY" \
    "https://api.github.com/repos/$REPO/releases" -o "$RELEASE_JSON"
fi
RELEASE_ID=$(python3 -c "import json;print(json.load(open('$RELEASE_JSON'))['id'])")
ASSET_ID=$(python3 -c "
import json
d = json.load(open('$RELEASE_JSON'))
a = [x for x in d.get('assets', []) if x['name'] == '$APK_NAME']
print(a[0]['id'] if a else '')" 2>/dev/null || echo "")
if [ -n "$ASSET_ID" ]; then
  curl -s -X DELETE -u "$GH_USER:$GH_TOKEN" "https://api.github.com/repos/$REPO/releases/assets/$ASSET_ID"
fi
curl -s -X POST -u "$GH_USER:$GH_TOKEN" -H "Content-Type: application/vnd.android.package-archive" \
  --data-binary @"$APK_NAME" \
  "https://uploads.github.com/repos/$REPO/releases/$RELEASE_ID/assets?name=$APK_NAME" \
  -o /tmp/f1re-asset.json -w "  upload: HTTP %{http_code}\n"
python3 -c "import json;d=json.load(open('/tmp/f1re-asset.json'));print('  asset:',d.get('name'),d.get('size'),'bytes')"

# 6. purge jsDelivr（update.json 缓存最长 12 小时，必须刷新）
echo "[6/6] 刷新 jsDelivr 缓存..."
curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"path\":[\"gh/$REPO@main/update.json\"]}" \
  https://purge.jsdelivr.net

echo ""
echo "完成！Release: https://github.com/$REPO/releases/tag/v$NEW_VER"
echo ""
echo "验证命令："
echo "  curl -s https://raw.githubusercontent.com/$REPO/main/update.json | head -3"
echo "  curl -s -o /dev/null -w '%{http_code}' https://cdn.jsdelivr.net/gh/$REPO@v$NEW_VER/$APK_NAME"
