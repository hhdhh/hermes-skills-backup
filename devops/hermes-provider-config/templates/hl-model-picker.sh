#!/bin/bash
# hl — Hermes model picker (shell-side)
# 列出 ~/.hermes/config.yaml 里 model.aliases 注册的所有模型,选一个启动 hermes chat
#
# 用法:
#   hl                列出可用 alias (默认就是 list)
#   hl -l | --list    同上
#   hl -h | --help    帮助
#   hl <alias>        用该 alias 启动 hermes chat (透传其余参数)
#   hl <alias> -q "x"  →  hermes chat -m <alias> -q "x"
#
# 来源: 2026-08-14 session,作为 hermes-provider-config 的支持文件。复制到
# ~/.local/bin/hl 并 chmod +x 即可用。脚本知道两个 YAML 缩进事实:
#   1. model.aliases 下的 alias 名是 4 spaces 缩进
#   2. alias 内部字段是 6 spaces 缩进
# 如果你的 config.yaml 缩进不同,需要调整 grep 正则。

set -e

ALIASES_FILE="${HOME}/.hermes/config.yaml"

list_aliases() {
    echo "━━━ 可用 alias (from $ALIASES_FILE) ━━━"
    if command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" 2>/dev/null; then
        python3 - "$ALIASES_FILE" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1])) or {}
aliases = (cfg.get('model') or {}).get('aliases') or {}
primary_model = (cfg.get('model') or {}).get('default', '?')
primary_prov  = (cfg.get('model') or {}).get('provider', '?')
fallback = cfg.get('fallback_providers') or []

if not aliases:
    print('  (model.aliases 为空)')
for i, (name, body) in enumerate(aliases.items(), 1):
    is_primary = body.get('model') == primary_model and body.get('provider') == primary_prov
    star = '★' if is_primary else ' '
    desc = f"{body.get('model','?')}  via  {body.get('provider','?')}"
    if body.get('base_url'):
        desc += f"  @  {body['base_url']}"
    print(f"  {star} {i}. {name:<20} {desc}")

if fallback:
    print()
    print(f"  Fallback chain ({len(fallback)}):")
    for i, e in enumerate(fallback, 1):
        print(f"     {i}. {e.get('model','?')}  via  {e.get('provider','?')}", end='')
        if e.get('base_url'):
            print(f"  @  {e['base_url']}", end='')
        print()
PY
    else
        # 无 PyYAML 时的 grep 兜底: 抓出 alias 名
        grep -E "^    [a-zA-Z0-9_-]+:$" "$ALIASES_FILE" | sed 's/^    /  /'
    fi
    echo
    echo "  ★ = 当前 primary"
}

case "${1:-}" in
    "")
        list_aliases
        ;;
    -l|--list)
        list_aliases
        ;;
    -h|--help)
        cat <<EOF
hl — Hermes model picker

用法:
  hl                列出可用 alias
  hl -l             同上
  hl -h             本帮助
  hl <alias>        启动 hermes chat -m <alias>
  hl <alias> [args] 透传 args 给 hermes chat

示例:
  hl minimax        ← primary
  hl autolife-gpt55 ← 自定义别名
  hl autolife-gpt55 -q "解释一下这段代码"
EOF
        ;;
    *)
        NAME="$1"
        # alias 名在 model.aliases 下,缩进 4 spaces
        if ! grep -qE "^    ${NAME}:" "$ALIASES_FILE" 2>/dev/null; then
            echo "❌ alias '$NAME' 不存在 (or wrong indent)"
            echo
            list_aliases
            exit 1
        fi
        shift
        exec hermes chat -m "$NAME" "$@"
        ;;
esac