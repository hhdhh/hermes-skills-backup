# RustFS 对象存储传输

<!-- capability_id: autolife-ops.rustfs-transfer | revision: 1 | status: active -->
<!-- 来源: RustFS 使用方法（Linux）（飞书语料） -->

## R — 原文

> env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy bash ./rustfs.sh setup
> —— 《RustFS 使用方法（Linux）》

## I — 自述

RustFS 是 S3 兼容的对象存储，用于机器人工作站数据回传（日志包/证据包/大文件）。CLI 封装在 rustfs.sh：首次 setup 建配置，之后 download/upload 子命令操作。

关键坑是代理：工作站上配的本地代理（HTTP_PROXY 等环境变量）会劫持 rclone 到 RustFS 的连接导致失败。所有 rustfs.sh 操作都要用 `env -u` 剥掉全部代理变量（大小写共 6 个）再执行，一次性内联，不改全局配置。

传输完成后必须校验：下载后核对文件完整性（大小/校验和），不只看命令退出码。

## A1 — 书中案例

**案例类型：书中亲历案例**（代理干扰排障，来源：RustFS 使用方法）

- 输入/问题：工作站上 rustfs.sh setup 反复超时失败
- 方法执行：检查环境变量发现 HTTP_PROXY/HTTPS_PROXY 指向本地代理 → rclone 连内网 RustFS 被代理劫持 → env -u 剥离 6 个代理变量后重跑
- 结论：setup 成功；后续所有操作统一带 env -u 前缀

## A2 — 未来触发 ★

**情境：**

1. 机器人工作站往 RustFS 传日志/证据/数据包
2. rustfs.sh/rclone 报连接超时或认证错（代理干扰）
3. 大文件批量回传后核对完整性
4. 新工作站首次配置 RustFS 客户端

**语言信号：**

- "rustfs" / "上传到 rustfs" / "下载数据包"
- "rclone 超时" / "连不上对象存储"
- "代理干扰" / "proxy 报错"
- EN: "rustfs upload" / "rclone timeout behind proxy"

**区分：**

- ≠ s3-object-storage-cli / rclone 系列通用技能：本卡是 AutoLife 内网 RustFS 的具体用法+代理坑
- ≠ autolife-robot-manager-toolbox：那讲工具箱全量；本卡是单个传输工具专项
- ≠ 网络 diagnosis：连不上先剥代理试一次再谈网络诊断

## E — 可执行步骤

**输入契约**：操作类型（setup/download/upload，必填）；目标路径/AK-SK（setup 时必填，从配置管理获取，不聊天传递）。

**Step 1 首次 setup（仅一次）**：
```
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy bash ./rustfs.sh setup
```
按提示填 endpoint/AK/SK（凭证只进配置文件，不进聊天/日志）
**Step 2 日常传输（同样带 env -u）**：
```
env -u HTTP_PROXY -u ... bash ./rustfs.sh upload <本地路径> <目标>
env -u HTTP_PROXY -u ... bash ./rustfs.sh download <目标> <本地路径>
```
**Step 3 校验**：下载后 `md5sum`/`ls -la` 核对大小与校验和；上传后 list 确认对象存在
**判停点**：剥代理后仍超时 → 查与 RustFS 服务器的网络可达（ping/nc 端口）；认证错 → 核对 AK/SK，不在命令行明文重试

**输出契约**：传输清单（文件名+大小+校验和）+ 成功/失败状态。

## B — 边界

- **不适用**：机器人本体故障；NetBird mesh；飞书文件传输（lark-im）
- **反场景**：为图省事关掉系统代理再操作（影响其他服务）；凭证写进命令行历史
- **失败模式**：只剥大写不剥小写（6 个都要）；传完不校验；setup 重复跑覆盖配置
- **相邻易混**：公网 S3/MinIO 通用操作（通用 rclone 技能）≠ 内网 RustFS 专项（本卡）
