#!/bin/bash
# check_app_window.sh — macOS GUI app 排错瑞士军刀
# 用法: ./check_app_window.sh "AppName" ["/path/to/Some.app"]
#
# 一次性跑完 6 项核心诊断, 给出症状 + 走哪个分支
# 作者: 灰灰 @ 2026-08-06 (NoMachine 实战沉淀)

set -e

APP_NAME="${1:?Usage: $0 AppName [/path/to/App.app]}"
APP_PATH="${2:-/Applications/${APP_NAME}.app}"

echo "═══════════════════════════════════════════════════════"
echo "macOS GUI App 排错: ${APP_NAME}"
echo "═══════════════════════════════════════════════════════"
echo ""

# 1. 进程状态
echo "━━━ 1. 进程状态 (ps aux) ━━━"
PIDS=$(ps aux | grep -i "${APP_NAME}" | grep -v grep | grep -v "$0" | awk '{print $2}' | tr '\n' ' ')
if [ -z "$PIDS" ]; then
  echo "❌ 没有 ${APP_NAME} 相关进程"
  echo "   跳到 app 启动失败类技能 (不是本 skill 范围)"
  exit 0
fi
ps aux | grep -i "${APP_NAME}" | grep -v grep | grep -v "$0"
echo ""

# 2. 窗口注册
echo "━━━ 2. 窗口注册 (osascript) ━━━"
WIN_OUT=$(osascript -e "tell application \"System Events\" to get name of every window of (every process whose name contains \"${APP_NAME}\")" 2>&1)
if [ -z "$WIN_OUT" ] || [ "$WIN_OUT" = "," ] || [ "$WIN_OUT" = ",," ]; then
  echo "❌ 进程没创建窗口 (返回: '${WIN_OUT}')"
  WINDOW_OK=0
else
  echo "✅ 有窗口: ${WIN_OUT}"
  WINDOW_OK=1
fi
echo ""

# 3. LSUIElement
echo "━━━ 3. LSUIElement 标志 (agent app 设计) ━━━"
LSUI=$(defaults read "${APP_PATH}/Contents/Info.plist" LSUIElement 2>/dev/null || echo "not_set")
if [ "$LSUI" = "1" ] || [ "$LSUI" = "true" ]; then
  echo "⚠️  LSUIElement=true (菜单栏 app, 不应自动出窗口)"
  echo "   → 主人应该看到菜单栏图标, 点它出窗口"
  MENU_BAR_APP=1
else
  echo "✅ LSUIElement=${LSUI} (普通 app, 应该自动出窗口)"
  MENU_BAR_APP=0
fi
echo ""

# 4. 进程归属 (launchd 守护?)
echo "━━━ 4. 进程归属 (是否 launchd 守护) ━━━"
FIRST_PID=$(echo "$PIDS" | awk '{print $1}')
ps -o pid,user,comm -p "$FIRST_PID" 2>/dev/null
CURRENT_USER=$(whoami)
PROC_USER=$(ps -o user -p "$FIRST_PID" 2>/dev/null | tail -1)
if [ "$PROC_USER" != "$CURRENT_USER" ]; then
  echo "⚠️  进程跑在 user=${PROC_USER} 下, 不在 ${CURRENT_USER} 下"
  echo "   → launchd 守护, killall/sudo kill 可能杀不掉"
  LAUNCHD_DAEMON=1
else
  echo "✅ 进程属于当前 user=${CURRENT_USER}"
  LAUNCHD_DAEMON=0
fi
echo ""

# 5. DiagnosticReports
echo "━━━ 5. DiagnosticReports (崩溃日志) ━━━"
CRASH_COUNT=$(ls -lt ~/Library/Logs/DiagnosticReports/ 2>/dev/null | grep -i "${APP_NAME}" | wc -l | tr -d ' ')
if [ "$CRASH_COUNT" = "0" ]; then
  echo "✅ 没有崩溃日志"
else
  echo "⚠️  有 ${CRASH_COUNT} 个崩溃日志 (最近 10 个):"
  ls -lt ~/Library/Logs/DiagnosticReports/ 2>/dev/null | grep -i "${APP_NAME}" | head -10
fi
echo ""

# 6. log show 自终止模式
echo "━━━ 6. log show 自终止模式 (最近 5 分钟) ━━━"
KILL_PATS=$(log show --predicate "process == \"${APP_NAME}\"" --last 5m --style compact 2>&1 | \
  grep -iE "tcc|terminate|exit|denied|fault|reason|windows open yet" | head -20)
if [ -z "$KILL_PATS" ]; then
  echo "✅ 没看到自终止模式"
else
  echo "⚠️  发现以下自终止信号:"
  echo "$KILL_PATS"
  echo ""
  echo "模式识别:"
  echo "$KILL_PATS" | grep -q "TCCAccessRequest" && echo "  → 模式 A: TCC 自终止 (去系统设置开对应权限)"
  echo "$KILL_PATS" | grep -q "No windows open yet" && echo "  → 模式 B: AutomaticTermination 'No windows open yet' (NSStatusItem/NSWindow 创建失败)"
fi
echo ""

# 综合判断
echo "═══════════════════════════════════════════════════════"
echo "综合判断"
echo "═══════════════════════════════════════════════════════"

if [ "$WINDOW_OK" = "1" ]; then
  echo "✅ 有窗口但主人没看到 → 试 ⌘+Tab / 检查 Mission Control / 全屏外"
elif [ "$MENU_BAR_APP" = "1" ]; then
  echo "⚠️  菜单栏 app, 主人应该看菜单栏右上角图标"
  echo "   如果主人看不到图标 → NSStatusItem 创建失败, 走模式 B 修复路径"
elif [ "$LAUNCHD_DAEMON" = "1" ]; then
  echo "⚠️  launchd 守护残留, 用 launchctl kill"
  echo "   → launchctl list | grep -i ${APP_NAME} 找 label"
else
  echo "⚠️  普通 app 启动了但没窗口 → 看 log show 输出, 走模式 A/B 修复路径"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "完整 SKILL: ~/.hermes/skills/devops/macos-app-no-window-debug/SKILL.md"
echo "═══════════════════════════════════════════════════════"