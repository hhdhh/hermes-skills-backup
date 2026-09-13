# launchd 给第三方 Skill 装定时任务（UUMit 等场景）

> 2026-08-15 灰灰立 · 给 UUMit 能力套件 5 个后台任务登记时踩的坑（4 command_task 走 launchd，1 agent_session_task 走 hermes cron）。

## 用 launchd 装第三方命令的"3 步曲 + 1 回读"模板

任何第三方 Skill 给出的 `cron` 表达式 + `command_abs`，登记进 macOS launchd 都按这个模式：

```bash
# Step 1: plutil 写 plist（不用 sed — 见 hermes-gateway-admin 既有教训）
cat > ~/Library/LaunchAgents/com.<vendor>.<task>.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>          <string>com.<vendor>.<task></string>
    <key>ProgramArguments</key>
    <array>
        <string><绝对路径:node 或 python3></string>
        <string><绝对路径:脚本入口></string>
        ... <args>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Minute</key>     <integer>0</integer>
        <key>Hour</key>       <array>0 4 8 12 16 20</array>     <!-- 0 */4 * * * 的翻译 -->
    </dict>
    <key>StandardOutPath</key>  <string><log绝对路径></string>
    <key>StandardErrorPath</key> <string><log绝对路径></string>
    <key>RunAtLoad</key>       <false/>                          <!-- 不要 startup 触发，只按周期跑 -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>UUMIT_SKILL_DIR</key> <string><skill根></string>     <!-- 第三方 skill 需要的 env 一并塞 -->
    </dict>
</dict>
</plist>
EOF

# Step 2: 3 件套 install
plutil -lint <plist>                                       # 语法 OK（必须先过）
launchctl bootstrap gui/$(id -u) <plist>                   # launchd 接受 = 静默 0 退出
launchctl print gui/$(id -u)/com.<vendor>.<task> | grep state   # 看 state（not running 是待机 = 正常）

# Step 3: 回读校对（铁律 — 跟源代码给的 cron 表达式逐字比对）
/usr/libexec/PlistBuddy -c "Print :StartCalendarInterval" <plist>
```

## `StartCalendarInterval` 不能用 `*/N`（最关键坑）

launchd 的 `StartCalendarInterval` **不支持 cron 的 `*/N` 语法**。必须把 hour/minute **全部展开**写成数组：

| 官方 cron 表达式 | 启动时刻 | launchd `StartCalendarInterval` 翻译 |
|---|---|---|
| `0 * * * *`（每小时整点） | :00 | `<key>Minute</key><integer>0</integer>`（只有 Minute 不写 Hour） |
| `0 */4 * * *`（每 4 小时整点） | 0/4/8/12/16/20 | `<key>Minute</key><integer>0</integer>` + `<key>Hour</key><array>0 4 8 12 16 20</array>` |
| `0 */3 * * *`（每 3 小时整点） | 0/3/6/9/12/15/18/21 | `<key>Minute</key><integer>0</integer>` + `<key>Hour</key><array>0 3 6 9 12 15 18 21</array>` |
| `0 */6 * * *`（每 6 小时整点） | 0/6/12/18 | `<key>Hour</key><array>0 6 12 18</array>` |
| `30 */2 * * *`（每 2 小时半点） | 0:30/2:30/4:30... | `<key>Minute</key><integer>30</integer>` + `<key>Hour</key><array>0 2 4 6 8 10 12 14 16 18 20 22</array>` |

**铁律**：登记前先用 `PlistBuddy -c "Print :StartCalendarInterval"` 回读，跟源代码的 cron 表达式 1:1 比对，**严禁**"我想当然每 6 小时"自己翻译。

**常见误译自查**：
- `0 */4 * * *` 不要写成 `0 0 * * *`（每天 0 点 — 错！）
- `0 * * * *` 不要写成 `0 0 */1 * *`（不是有效语法）
- launchd 不会报"频率错"——它**会接受错误表达**然后按错的时间跑，**只能靠回读校对发现**

## `state = not running` ≠ 翻车

刚 `launchctl bootstrap` 完后立刻看 `state`：
- **有 `RunAtLoad=true`** → 应在 `running`（没过 startup 时间会先 `waiting`）
- **`RunAtLoad=false`** + 没到下个时间点 → **正常待机** `not running`

`not running` 不是 EINVAL 翻车。EINVAL 是 **bootstrap 那一行就报错**（exit 5 / "Bootstrap failed: 5"），回读完全没有 job 存在。

7/4 主人栽过的 launchd 拒收坑（gateway plist EINVAL）跟这里**完全无关**——那个错连 `launchctl print` 都查不到 job。这次的"4 个 plist 全 bootstrap 静默成功、`state = not running`"是**正确的 standby**，只是还没到下一个整点。

## `agent_session_task` 绝对不能进 launchd 裸跑

某些第三方 Skill（比如 UUMit 的 `market_auto_bid`）的 `task_type` 是 `agent_session_task`，**故意没有 command_abs**——它必须由"宿主唤起的 Agent 会话"执行：

- 脚本只产工单（候选+待交付订单）
- 真正的接单/交付须 Agent 读工单 → 逐单判定 → 生成内容 → 回调 apply/deliver
- 若把它的 `inner_command_abs`（比如 `market-run`）当普通裸命令登记进 launchd/cron：**每轮只会产工单、永不接单交付** = 假上线

**正确做法：用 hermes cronjob 注册**（你机器上有），到点会拉起一个真 Agent 会话跑完整闭环：

```python
cronjob(action='create',
    name='<skill>-<task>',
    prompt='执行一轮 XXX 闭环（这是定时到点要跑的固定工作）：① xxx...',
    schedule='0 * * * *',         # 跟官方 schedule.cron 完全一致
    deliver='origin',             # 结果回到当前会话
    model={'provider': 'minimax', 'model': 'minimax/MiniMax-M3'})
```

登记后回读：`hermes cron list` → 看到 `state: scheduled`, `next_run_at` 正确。

## macOS 没 `timeout` 命令 — 用 background 进程

`timeout 480 node ...` 在 macOS 默认没装（要 brew install coreutils）。**改用**:

```python
terminal(background=true, notify_on_complete=true)
# 命令本身（不带 timeout）
```

结束后系统会推一次 completion notification。要看输出用 `process(action='log'/'poll'/'wait')`。

## 给 Skill 装后台的"实操报告"模板（回报用）

```
✅ <任务中文名> — macOS launchd — <频率中文>
   - 频率实建: StartCalendarInterval [0,4,8,12,16,20] Minute=0 (= 0 */4 * * *)
   - 命令实建: "/path/node" "/path/script.js" status
   - 回读校对: 跟官方 cron 表达式完全一致 ✅
   - 标准输出: <log 路径>（launchd 原生回显）
   - 下次启动: <下一次整点>

⚠ <agent_session_task 那个> — Hermes cron（Agent 驱动）— 每小时整点
   - 实建频率: 0 * * * *
   - 唤起形态: Agent 会话 + driver_prompt 投喂（不是裸命令）
   - 下次启动: <next_run_at>
```

避免用"看起来开了"虚报。**bootstrap exit 0 + state 正确 + 回读频率对 = 真开了**。

## Pitfalls（跟 hermes-gateway-admin 既有的 EINVAL 教训并列）

1. **launchd `StartCalendarInterval` 不支持 `*/N`** — 必须展开 array。
2. **`state = not running` 是正常待机**，不是 EINVAL 翻车。
3. **`agent_session_task` 不能进 launchd 裸跑** — 用 hermes cron job + driver_prompt。
4. **macOS 没 `timeout`** — 用 `terminal(background=true, notify_on_complete=true)` + `process` 工具看结果。
5. **不要 `RunAtLoad=true`** — 除非你确实要 startup 触发，第三方 scheduled 任务是按周期跑的。
6. **不要漏 `StandardOutPath`/`StandardErrorPath`** — launchd 启动会立即写日志，路径不可写 = 拒收。
7. **第三方 skill 需要的 env（如 `UUMIT_SKILL_DIR`）必须塞 `EnvironmentVariables`** — 不然脚本找不到自己的根。
8. **回读频率 ≠ 安装成功** — 不回读 = 默认翻译可能错（"每 6 小时"误成"每天 0 点"），launchd 不报错、按错时间跑。
9. **`-background-launched` id 必须用后台任务的内部 id，不是 display_name** — `display_name` 是中文给主人看的（"账户巡航对账"），id 是后端真名（`cruise_status`）。装完用 `install.js --background-launched <id>` 记本地状态，**顺序是先真登记、后记状态**——否则只是本地假标记。
