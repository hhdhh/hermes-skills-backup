---
name: autolife-capsule-deployment
version: 1.0.0
description: AutoLife S1 太空舱（饮品/零食）环境部署与部署验证：snack_bot_env 环境包安装、flow...
---

# AutoLife 太空舱环境部署与验证

> 完整描述：AutoLife S1 太空舱（饮品/零食）环境部署与部署验证：snack_bot_env 环境包安装、flow capsule 配置切换、ai-grasp/flow 服务核验。当主人问"太空舱部署成功了吗"、"装太空舱环境"、"切 capsule 流程"时使用。

> 机器人 = AutoLife S1，SSH 工具 `~/.hermes/workspace/robssh.py`（见 skill: autolife-remote-repair）。
> 权威流程文档（公司飞书）：《Autolife 太空舱饮品零食配置流程》——本地提取件在 `~/.hermes/workspace/feishu-work-knowledge/corpus/0014-docx-*.txt`，遇到本技能没覆盖的步骤（标定、建图、货架点位）去那里查。

## 双环境铁律

太空舱用**两个独立 conda 环境**，升级/排障别混：
- `robot_env`：导航 / GV / **flow**（`autolife_robot_flow`，含 capsule.xml）
- `snack_bot_env`：AI 抓取 / 识别（`autolife_ai`，含 AI SDK 权重）

两者都装在 `~/miniconda3/envs/`，SDK 各自独立升级。

## 部署步骤（环境包）

1. 下载 `envs/` 目录下**全部分卷**（snack_bot_env.tar.gz.part-00000…，约 33G）+ `run.sh` + `SHA256SUMS`，scp 到机器人 `~/envs/`。缺任意一个分卷会导致环境初始化失败。
2. 机器人上执行 `cd ~/envs && ./run.sh`（合并分卷 → 解压到 `~/miniconda3/envs/snack_bot_env`）。解压后约 31G。
3. 验证：`~/miniconda3/envs/snack_bot_env/bin/pip list | grep -E "torch|ultralytics|transformers"`；权重目录 `~/miniconda3/envs/snack_bot_env/autolife_ai_sdk_weights/`（resnet50 / dinov2 / checkpoints）应在位。

## 部署步骤（flow 切太空舱）

flow 包在 robot_env 的 site-packages 里：
`~/miniconda3/envs/robot_env/lib/python3.12/site-packages/autolife_robot_flow/`

```bash
cp ./flow/capsule.xml.example ./flow/capsule.xml
sed -i 's/flow_xml_name = "main.xml"/flow_xml_name = "capsule.xml"/' settings.toml
```

改前先 pull 备份（标准姿势见 autolife-remote-repair）。

## 部署验证清单（问"部署成功了吗"就跑这个）

对目标机逐项核验（只读，直接做）：

```
1. 环境   ls ~/miniconda3/envs/ 有 snack_bot_env；pip 关键包在；weights 目录在
2. flow   grep flow_xml_name <robot_env site-packages>/autolife_robot_flow/settings.toml == capsule.xml
          flow/ 下有 capsule.xml（不是只有 .example）
3. 服务   systemctl --user list-units | grep -E "ai-grasp|flow-service"
          ai-grasp（snack_bot_env）+ flow-service（robot_env）均 active running
4. 进程   ps aux | grep -E "autolife_ai|autolife_robot_flow" 确认 conda run -n 对应环境正确
5. 日志   按需 journalctl --user -u ai-grasp-service 看有无报错
```

另外两项属于后续现场步骤，不在部署核验内：动力学标定（settings.toml 的 force_enable / force_safety_enabled，默认 false）、建图导航与货架点位实测。汇报时把这两项列为"待确认"，别判成失败。

## 坑

- **分卷合并产物 33G 留在 ~/envs/**：run.sh 合并出的 tar.gz 和分卷都不自动清理。环境确认稳定后提醒主人可删（删前确认解压完整、服务正常）。
- flow 配置不在机器人 home 目录——find ~ 找 settings.toml 会漏，它藏在 robot_env 的 site-packages/autolife_robot_flow/ 里。同理 capsule.xml 也在包目录下。
- 机器刚开机 load average 偏高（服务冷启动）属正常，别当故障上报。
- `systemctl --user --failed` 里的 ubuntu-report.path / update-notifier-crash.path 是 Ubuntu 杂项，与机器人业务无关，忽略。
- 判断 ai-grasp 跑对环境：看进程命令行的 `conda run --no-capture-output -n snack_bot_env`——抓取必须吃 snack_bot_env，吃 robot_env 就是装错环境。
