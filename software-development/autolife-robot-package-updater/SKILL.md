---
name: autolife-robot-package-updater
description: Use when building or reviewing Autolife robot package upd...
---

# Autolife 机器人软件包安全更新

> 完整描述：Use when building or reviewing Autolife robot package updates.

## 触发条件

为 Autolife/S2 机器人从飞书网盘、公司 HTTPS 或本地发布包更新 `.whl`/`.conda` 时使用。

## 流程

1. 从《S2软件版本检查表》确认目标包版本，但不要把表格发布地址或聊天附件直接当成可信完整发布。
2. 只从固定、批准的飞书 Drive 文件夹或明确 HTTPS URL 发现发布包。包名必须为 `autolife-release-<release_id>.zip`；按 release ID 比较，不能按修改时间猜最新版。
3. 发布包必须有唯一 `release.json`，声明 schema、release ID、channel、architecture、Python major.minor，以及每个文件的名称、SHA-256、包名、版本、kind 和目标 Conda 环境。
4. ZIP 解压前拒绝：绝对/`..` 路径、反斜杠绕过、符号链接、重复/大小写冲突路径、文件-目录冲突、过多条目、过大展开体积和异常压缩比。
5. 拒绝未列入 manifest 的任何 `.whl`/`.conda`；逐文件比对 SHA-256。
6. 固定环境：face → `face_detection_env`，robot → `robot_env`，AI/snack → `snack_bot_env`。逐个使用环境 Python/Conda 的绝对路径安装，禁止通配符。
7. 应用前检查架构、各环境 Python 版本和可执行文件。默认 preview；实际应用必须 `--apply` 与明确确认。
8. 安装前 `pip freeze --all`，写入权限 0700 的事务目录，以本地 0600 HMAC key 签名事务。不要覆盖现场 `settings.toml`、JSON、Flow、校准或数据集。
9. 安装后用 `importlib.metadata.version` 验证每个目标包。任意异常都尝试恢复 freeze，并卸载更新前不存在的新包。清晰报告部分/失败回滚。
10. 测试必须包含：真实飞书下载到 staging、没有 manifest 的 ZIP 被拒绝、真实临时 wheel 安装+签名回滚、哈希篡改、ZIP traversal/symlink/duplicate/collision、错误架构/Python、环境隔离、unexpected exception rollback、Web UI 无 apply API。

## 飞书 CLI 注意事项

- 搜索需要 `search:docs:read`。
- 文件下载可通过现有 `drive:file:download`；文件夹列举可能额外要求 `space:document:retrieve`，且租户应用若待审批会授权失败。
- `lark-cli drive +download` stdout 可能先打印 `Downloading:`，再输出 JSON；从第一个 `{` 解析，并读取 `data.saved_path`。
- 必须验证 CLI 返回路径正好等于工具创建的 staging 目标，拒绝 staging 外路径。

## 验证

运行项目全量 unittest、Ruff、ShellCheck、JS syntax；从最终 archive 重新解压后再运行全套测试。真实硬件/ROS/业务流程仍需目标机器人现场验收。
