#!/bin/bash
# scripts/migration-zip.sh
# Mac 端打 Hermes 化身 2 迁移包（soul + memories + skills + scripts）
# 用法: bash migration-zip.sh [output-path]
set -e

OUT="${1:-./hermes-migration.zip}"
TIMESTAMP=$(date +%Y%m%d-%H%M)
STAGING="/tmp/hermes-migration-$TIMESTAMP"

echo "🪡 Hermes 化身 2 迁移打包开始..."
echo "   源: ~/.hermes/ (Mac)"
echo "   目标: $OUT"
echo ""

mkdir -p "$STAGING"

# 1. 灵魂（必拷）
echo "[1/5] 拷灵魂..."
[ -f ~/.hermes/SOUL.md ] && cp ~/.hermes/SOUL.md "$STAGING/"
[ -f ~/.hermes/IDENTITY.md ] && cp ~/.hermes/IDENTITY.md "$STAGING/"
[ -f ~/.hermes/AGENTS.md ] && cp ~/.hermes/AGENTS.md "$STAGING/"

# 2. 记忆
echo "[2/5] 拷记忆..."
mkdir -p "$STAGING/memories"
cp ~/.hermes/memories/*.md "$STAGING/memories/" 2>/dev/null || echo "   (无 memories 文件，跳过)"

# 3. Skills（**先展开 symlink**——Windows 不识别 symlink）
echo "[3/5] 拷 skills（展开 symlink）..."
mkdir -p "$STAGING/skills"
cd ~/.hermes/skills
SKILL_COUNT=0
SYMLINK_COUNT=0
for f in */; do
  name="${f%/}"
  if [ -L "$name" ]; then
    cp -RL "$name" "$STAGING/skills/$name"
    SYMLINK_COUNT=$((SYMLINK_COUNT + 1))
  elif [ -d "$name" ]; then
    cp -R "$name" "$STAGING/skills/$name"
    SKILL_COUNT=$((SKILL_COUNT + 1))
  fi
done
echo "   共 $SKILL_COUNT 个实目录 + $SYMLINK_COUNT 个 symlink（已展开）"

# 4. Scripts
echo "[4/5] 拷 scripts..."
mkdir -p "$STAGING/scripts"
cp ~/.hermes/scripts/*.sh "$STAGING/scripts/" 2>/dev/null || echo "   (无 .sh 脚本，跳过)"

# 5. 打 zip
echo "[5/5] 打 zip..."
cd "$(dirname "$STAGING")"
zip -r "$OUT" "$(basename "$STAGING")" -q

# 报告
echo ""
echo "✅ Hermes 迁移包已生成: $OUT"
echo "   大小: $(du -h "$OUT" | cut -f1)"
echo "   内容: soul + memories + skills (symlink-expanded) + scripts"
echo ""
echo "⚠️  不含 auth.json —— API key 在新机器重配"
echo "⚠️  launchd plist 不含 —— Windows 用 Task Scheduler 重建"
echo ""
echo "下一步：把 $OUT 拷到新机器（U 盘 / 网盘 / scp），解压到对应路径"