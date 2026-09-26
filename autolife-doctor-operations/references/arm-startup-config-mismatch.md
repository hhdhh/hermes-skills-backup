# arm 启动报"找不到 robot_vX_Y.json"——配置版本与 SDK 不匹配

> 出现于 2026-09-17 在 321（v2_2 SDK）上：arm service 启动期报 `error: 找不到文件 .../descriptions/autolife_s1/dynamics/robot_v2_4.json`，但 arm 全程仍能跑（FPS 稳、关节 init 完成）。该 error 是**启动期一次性**，每次 service 重启刷一次。

## 三层"机器人版本"——任一对不上就报

| 层 | 决定因素 | 怎么看 |
|----|---------|--------|
| **硬件** | 实际机器人本体（v2_2 / v2_4 / v2_5_lk...） | 机器铭牌 / 工单 / 装机记录 |
| **SDK 部署** | `~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_sdk/` 里实际打包的描述文件 | `ls descriptions/autolife_s1/{configs,dynamics,urdfs}/` 哪些版本是**真 json/urdf**（不是 `.example`） |
| **配置 active_robot_version** | `autolife_robot_arm/settings.toml` 第 4 行 `active_robot_version = "robot_vX_Y"`（SDK 包内置文件，部署时被 sed 过） | `grep active_robot_version <robot_env>/lib/python3.12/site-packages/autolife_robot_arm/settings.toml` |

**根因**：arm action control 启动时去 `dynamics/robot_vX_Y.json` 读动力学参数；只要 SDK `dynamics/` 没这个真文件，就打 `找不到文件` error。三层里"配置"是软连接——最容易错位（部署脚本漏改、装机时型号填错）。

## 诊断路径

```bash
# 1. 看当前 active_robot_version
grep active_robot_version <robot_env>/lib/python3.12/site-packages/autolife_robot_arm/settings.toml

# 2. 看 SDK dynamics/ 哪些是部署的真文件（不带 .example 后缀）
ls <robot_env>/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/dynamics/

# 3. 看 SDK configs/ 哪些是部署的真文件（用来核对 SDK 整体版本矩阵）
ls <robot_env>/lib/python3.12/site-packages/autolife_robot_sdk/descriptions/autolife_s1/configs/

# 4. 看 SDK __init__.py 声明支持哪些版本（确认 active 值是否在合法集合里）
grep -E "robot_v" <robot_env>/lib/python3.12/site-packages/autolife_robot_sdk/__init__.py | head -20
```

## 决策树

```
active_robot_version 在 SDK configs/ 有真文件吗？
├── 否 → 100% 是配置错（部署时写错了版本号）→ 改 settings.toml
└── 是
    └── active_robot_version 在 SDK dynamics/ 有真文件吗？
        ├── 否 → 配置指向的是 partial SDK（configs 装了，dynamics 没装）
        │        → 只能退回 dynamics/ 实际有的最近版本（通常是 v2_2）
        └── 是
            └── 报错的文件路径和 active 写的不一致？→ 看具体 error 行，
                可能是 SDK 子路径（urdfs/srdfs/...）版本不全
```

321 的 case：active=v2_4，configs/v2_4.json ✓，dynamics/v2_4.json ✗（只有 .example），dynamics/ 真文件只有 v2_2.json → 决策树第二层 → 退回 v2_2。

## 修法（标准姿势）

```bash
# 1. 备份 settings.toml（必做，文件名带原版本号便于回滚）
cp -a <robot_env>/lib/python3.12/site-packages/autolife_robot_arm/settings.toml \
      <robot_env>/lib/python3.12/site-packages/autolife_robot_arm/settings.toml.bak.<机号>v<X>_<Y>

# 2. sed 一行改回 SDK 实际有的版本（不要 sed -i 多行，只动第 4 行）
sed -i 's/active_robot_version = "robot_v2_4"/active_robot_version = "robot_v2_2"/' \
    <robot_env>/lib/python3.12/site-packages/autolife_robot_arm/settings.toml

# 3. 验证改动只影响一行
grep -n 'active_robot_version' \
     <robot_env>/lib/python3.12/site-packages/autolife_robot_arm/settings.toml

# 4. 重启 service（arm-control-service 属 Guarded 之下但 settings.toml 不属于 prompt/RAG，单点 restart 即可；
#    如果还在移动机械臂，先确认安全）
systemctl --user restart arm-control-service.service
```

## 验证闭环

```bash
# 1. service 起来
systemctl --user status arm-control-service.service --no-pager | head -10
# 期望: Active: active (running) since ...

# 2. 启动后日志头应该是新版本号
journalctl --user -u arm-control-service.service --no-pager -S '<重启时间>'
# 期望: 看到 robot_v2_2 Available modules: [...]（不再是 v2_4）
# 期望: urdf 加载路径变成 robot_v2_2_simplified.urdf
# 期望: 不再有 "error: 找不到文件 ...robot_v2_4.json"

# 3. FPS 还在（说明 action control 没崩）
journalctl --user -u arm-control-service.service --no-pager -S '<重启后 30s>' | grep -E 'count fps'
# 期望: leg_waist ~200, neck ~200, left/right_arm ~303, stability ~200
```

## 容易混淆的"红鲱鱼"

- **`error: 找不到文件` ≠ service 崩溃**：action control 启动失败但 fall back 到默认或继续跑无该模块的版本，arm 心跳全稳。容易让人以为是"刷屏无害 warning"。但每次 service 重启都刷一条，污染日志 + 排查时混淆视听，**应该修**。
- **同款 error 也可能出现在 urdfs/srdfs/meshes/mjcfs 子目录**：`descriptions/autolife_s1/urdfs/robot_v2_4_simplified.urdf` 缺失也会触发类似 error。先看 error 行的具体文件名属于哪个子目录。
- **`mod_ultrasonic_rear_right not found` 不是本类错误**：那是 SDK 模块枚举 vs 硬件，根因不同（缺硬件或 hardware profile 写漏）。参考 [robot-recovery.md](robot-recovery.md) 故障 #1-11 找对应症状。
- **`Publisher count: 1 ≠ 有数据` 反例在 v2_4 vs v2_2 上同样适用**：如果改完 settings.toml 后，建图或 arm 莫名"没数据"，先 `ros2 topic hz` 实测，别被 publisher count 骗了。

## 何时升级去 v2_4 / v2_5_lk

如果主人或工单明确这台要跑 v2_4 功能（新功能/兼容新硬件），但 SDK `dynamics/` 没有真文件，**不要**手工 cp `.example` 改后缀就上——`.example` 内容可能跟 `.json` 真文件结构/字段不同（占位/模板），后果不可控。正确做法：

1. 通知研发/上游把真 json 打进 SDK 部署包（`dynamics/robot_v2_4.json`）
2. SDK 升级后重新部署 + 重启 arm-control-service

短期 workaround：维持 v2_2，loss 的功能单独验证是否影响当前业务。

## 改完之后要不要写飞书

是的——按 [evidence-and-feishu.md](evidence-and-feishu.md) 的归档流程，这种"配置文件版本号漂移"是非常容易在下次装机/重部署时复发的低层 bug，必须归档到云空间「机器人故障记录库（FAE·运营助手维护）」让同事也认得到这个模式。

