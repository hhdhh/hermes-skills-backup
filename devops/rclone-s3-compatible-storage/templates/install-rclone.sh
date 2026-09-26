#!/usr/bin/env bash
# rclone 升级/安装脚本 — 在用户自己的终端里跑这个(agent PTY 不能 sudo)
# 这个脚本会:
#   1. 检查现有 rclone 版本,有就备份无就跳过
#   2. 下载 rclone 官方最新版(latest,不是 current)
#   3. 解压到 /tmp
#   4. sudo 装到 /usr/bin/rclone (覆盖旧版)
#   5. 校验新版本
set -euo pipefail

echo "=========================================="
echo "  rclone 升级/安装脚本"
echo "=========================================="
echo ""

# 1. 看现有版本
if command -v rclone >/dev/null 2>&1; then
    CUR=$(rclone version 2>/dev/null | head -1 | awk '{print $2}')
    echo "ℹ️  当前 rclone 版本: $CUR (位置: $(which rclone))"
    sudo cp -p "$(which rclone)" "$(which rclone).bak.${CUR}" 2>/dev/null && \
        echo "✅ 旧版已备份: $(which rclone).bak.${CUR}" || \
        echo "⚠️  备份失败(可能没 sudo 权限),继续..."
else
    echo "ℹ️  未检测到 rclone,本次为全新安装"
fi
echo ""

# 2. 下载最新版
TMPDIR=$(mktemp -d)
cd "$TMPDIR"
echo "📥 下载 rclone 最新版..."
curl -fSL --retry 3 -o rclone.zip \
  https://downloads.rclone.org/rclone-current-linux-amd64.zip
echo "✅ 下载完成: $(ls -lh rclone.zip | awk '{print $5}')"
echo ""

# 3. 解压
echo "📦 解压..."
if ! command -v unzip >/dev/null 2>&1; then
    echo "⚠️  系统没装 unzip,正在装..."
    sudo apt-get update -qq && sudo apt-get install -y -qq unzip
fi
unzip -q rclone.zip
EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name 'rclone-v*' | head -1)
echo "✅ 解压到: $EXTRACTED_DIR"
echo ""

# 4. 安装
cd "$EXTRACTED_DIR"
echo "🔧 装到 /usr/bin/rclone (需要 sudo)..."
sudo cp -p rclone /usr/bin/rclone
sudo chmod 755 /usr/bin/rclone
echo "✅ 安装完成"
echo ""

# 5. 校验
echo "=========================================="
echo "  验证新版本"
echo "=========================================="
rclone version | head -3

# 6. 清理
cd ~
rm -rf "$TMPDIR"
echo ""
echo "🎉 搞定!"
