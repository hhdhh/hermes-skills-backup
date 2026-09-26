#!/usr/bin/env bash
# 在另一台 Linux 电脑上跑这个脚本,自动配好 rustfs + 可选上传
# 用法:
#   bash setup-rustfs-upload.sh                       # 只配置不上传
#   bash setup-rustfs-upload.sh /path/to/local        # 配置 + 上传这个目录
#
# 环境变量(可选,改桶/改子目录):
#   BUCKET=robot-289 REMOTE_PREFIX=2026-08-17/ bash setup-rustfs-upload.sh /data
set -euo pipefail

# ============== 你需要改的(不传则忽略) ==============
BUCKET="${BUCKET:-robot-shanghai-yuyu}"
REMOTE_PREFIX="${REMOTE_PREFIX:-290/}"
# =====================================================

RCLONE_CONF="$HOME/.config/rclone/rclone.conf"

echo "=========================================="
echo "  rustfs 上传配置脚本 (Linux)"
echo "=========================================="
echo ""

# ---- 1. 装 rclone(没装才装) ----
if ! command -v rclone >/dev/null 2>&1; then
    echo "[1/4] rclone 未安装,正在安装..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update -qq
        sudo apt-get install -y -qq rclone
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y epel-release
        sudo yum install -y rclone
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y rclone
    else
        echo "未识别的包管理器,改为官方脚本..."
        curl -fsSL https://rclone.org/install.sh | sudo bash
    fi
    echo "      安装完成: $(rclone version | head -1)"
else
    echo "[1/4] rclone 已存在: $(rclone version | head -1)"
fi
echo ""

# ---- 2. 写配置 ----
echo "[2/4] 写入配置 $RCLONE_CONF ..."
mkdir -p "$(dirname "$RCLONE_CONF")"
cat > "$RCLONE_CONF" <<'EOF'
[rustfs]
type = s3
provider = Other
env_auth = false
access_key_id = ab5OdfRfpKPBlEdWggee
secret_access_key = Gu6duziYfjO6Z2ckF50W5jS8u9daKrnMu70J9meM
endpoint = https://rustfs.gz.autolife.ai:8444
force_path_style = true
EOF
chmod 600 "$RCLONE_CONF"
echo "      配置完成"
echo ""

# ---- 3. 验证远端可达 ----
echo "[3/4] 验证远端..."
if rclone lsd "rustfs:$BUCKET" --no-check-certificate >/dev/null 2>&1; then
    echo "      ✅ 远端可达,桶 [$BUCKET] 存在"
else
    echo "      ❌ 连不上!检查:网络 / endpoint / AK/SK"
    exit 1
fi
echo ""

# ---- 4. 上传(如果传了路径) ----
if [ $# -ge 1 ] && [ -n "${1:-}" ]; then
    LOCAL="$1"
    if [ ! -e "$LOCAL" ]; then
        echo "❌ 本地路径不存在: $LOCAL"
        exit 1
    fi
    REMOTE="rustfs:${BUCKET}/${REMOTE_PREFIX}"
    echo "[4/4] 上传"
    echo "      源: $LOCAL"
    echo "      目标: $REMOTE"
    echo "      进度: -P / 8 并发 / 断点续传"
    echo ""
    rclone copy "$LOCAL" "$REMOTE" -P \
        --no-check-certificate \
        --retries 10 --retries-sleep 5s \
        --transfers 8
    echo ""
    echo "🎉 上传完成"
else
    echo "[4/4] 跳过上传(没传本地路径参数)"
    echo ""
    echo "用法示例:"
    echo "  bash $0 /path/to/local_dir           # 上传整个目录"
    echo "  BUCKET=robot-289 REMOTE_PREFIX=2026-08-17/ bash $0 /path/to/data"
fi
