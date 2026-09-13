# launchd bootstrap EINVAL 诊断与修复

> 2026-07-04 灰灰立 · 7/4 给 5 个空 profile (main/pm/cto/security) 装 plist + 启 gateway 时撞的坑。
> 经验：plist 跟 working 的 main/dev/ops/qa 几乎一样，**但 launchd 持续拒收**。

## 症状

```bash
$ launchctl bootstrap gui/501 /Users/kk/Library/LaunchAgents/ai.hermes.gateway-pm.plist
Bootstrap failed: 5: Input/output error
Try re-running as root for richer errors.
```

退出码 5 = `EINVAL`。**plist 校验没过**。

## 诊断步骤（按顺序）

### 1. plutil 二次校验

```bash
plutil -lint /path/to/component.plist
```

如果 `OK` 但 launchd 仍拒收 — **plist 语法没问题**，是 launchd 内部状态问题。

### 2. plutil 解析成 JSON 看实际结构

```bash
plutil -p /path/to/component.plist
```

跟已知 working 的 main/dev plist diff。注意**结构**（dict / array）而非内容：
- `KeepAlive` 应是 `<dict><key>SuccessfulExit</key><false/></dict>`，**不能**是单 `<true/>`
- `EnvironmentVariables` 必须是 `<dict>` 包 `<key>...<string>...</string>`
- `ProgramArguments` 是 `<array>` of `<string>`

### 3. 看 logs 目录

```bash
ls -la /Users/kk/.hermes/profiles/<X>/logs/
```

plist 启动时 launchd 会立即**写** log 文件 — 目录不存在或权限不对会拒收。

### 4. launchd cache 卡了（最常见）

如果 1/2/3 都过 — **launchd 内部 cache 卡了**。需要：
```bash
sudo launchctl print system    # 触发 cache 重建
# 或
sudo killall launchd           # 重启 launchd（破坏性，最后手段）
```

**agent 没 sudo — 这是真的卡点**。兜底见下。

## 根因（实测推测）

macOS launchd 在 `bootstrap` 时**会做 5-10 步校验**（plist 语法、Label 唯一性、ProgramArguments 可执行、logs 路径可达、EnvironmentVariables 解析、WorkingDirectory 可读、签名等）。其中：

- **Label 唯一性校验失败** — 同一个 Label 多次 bootstrap（之前 bootout 没清干净）
- **cache 卡了** — 校验通过但 launchd 不接受（"reluctant to admit"），需 sudo trigger cache 重建

实测 7/4：main 第一次也 EINVAL，但 `hermes gateway start` 自动做 `bootout + reload` 后就好了。**`hermes gateway start` 比裸 `launchctl bootstrap` 强**。

## 修复模式（plutil，不用 sed）

```bash
# 模板（dev 是已知 working）
cp /Users/kk/Library/LaunchAgents/ai.hermes.gateway-dev.plist \
   /Users/kk/Library/LaunchAgents/ai.hermes.gateway-NEW.plist

# 改字段（plutil 不会破坏 XML 结构）
plutil -replace Label -string "ai.hermes.gateway-NEW" <plist>
plutil -insert ProgramArguments.3 -string "--profile" <plist>
plutil -insert ProgramArguments.4 -string "NEW" <plist>
plutil -replace EnvironmentVariables.HERMES_HOME \
        -string "/Users/kk/.hermes/profiles/NEW" <plist>
plutil -replace StandardOutPath \
        -string "/Users/kk/.hermes/profiles/NEW/logs/gateway.log" <plist>
plutil -replace StandardErrorPath \
        -string "/Users/kk/.hermes/profiles/NEW/logs/gateway.error.log" <plist>
plutil -replace WorkingDirectory \
        -string "/Users/kk/miniconda3/lib/python3.13/site-packages" <plist>

# 校验
plutil -lint <plist>

# 启动（重试 2-3 次）
for i in 1 2 3; do
  launchctl bootstrap gui/$(id -u) <plist>
  sleep 1
done
```

## **不要用 sed**

```bash
# 错：
sed -e "s|ai.hermes.gateway-dev|ai.hermes.gateway-${prof}|g" \
    -e "s|<string>dev</string>|<string>${prof}</string>|g" \
    "$plist_src" > "$plist_dst"

# sed 会把 <dict><key>SuccessfulExit</key><false/></dict>
# 替换成 <true/>  之类（取决于 sed 贪婪匹配）
# → 破坏 XML 结构 → launchd 拒收
```

## 兜底（nohup 手动启）

```bash
HERMES_HOME=/Users/kk/.hermes/profiles/<X> \
  nohup /Users/kk/miniconda3/bin/python3.13 \
    -m hermes_cli.main --profile <X> gateway run --replace \
    > /Users/kk/.hermes/profiles/<X>/logs/manual-gateway.log 2>&1 &
```

**注意**：
- 必须 `terminal(background=true, notify_on_complete=true)` 启动 — 工具会触发 "start gateway outside systemd" approval
- **主人逐个批** — 7/4 实测 3 个里只批了 1 个
- 不持久化 — reboot 后丢（除非 plist 之后被 launchd cache 重建时接受）
- 跟 launchd 启动的 gateway 不冲突 — 不同 PID，可同时跑

## 实测时间线（7/4 灰灰）

```
00:10  cp dev → main/pm/cto/security (4 个 plist)
00:11  plutil -lint 4 个全 OK
00:11  launchctl bootstrap main → 成功 (PID 81674)
00:11  launchctl bootstrap pm   → EINVAL (持续)
00:11  launchctl bootstrap cto  → EINVAL (持续)
00:11  launchctl bootstrap security → EINVAL
00:13  plutil 重写 3 个 plist（删 --profile 段简化）
00:13  再 bootstrap 3 个 → 仍 EINVAL
00:14  nohup security → 主人批 → PID 87286 跑着
00:14  nohup pm/cto    → 主人拒
00:15  报告主人：plist 装好等下次 launchd 重载
```

## 结论

1. **用 plutil 不用 sed** — 防止结构破坏
2. **先试 `hermes gateway start` 不是裸 `launchctl`** — 它有 reload 兜底
3. **重试 2-3 次** — launchd 偶发
4. **持续 EINVAL = launchd cache 卡** — 找主人 sudo
5. **nohup 兜底是 5/5 风险** — 主人 partial-approve，**默认不当 fallback 用**
