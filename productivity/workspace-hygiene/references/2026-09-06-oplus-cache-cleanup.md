# 2026-09-06 macOS 存储清理：O+ Connect 与过期恢复暂存

## 场景

用户要求清理电脑存储。首轮审计发现：

- `~/.cache/hermes-trash-20260808`：约 11 GB，已经是一个月前建立的可恢复清理暂存区。
- 常规工具缓存（uv/npm/Homebrew/pip/应用缓存）：约 4 GB。
- `~/Library/Containers/com.oplus.devicespace.extension`：约 14 GB。

用户随后明确授权同时清理“安全回收约 15 GB”和“O+ 手机数据 14 GB”。

## O+ Connect 的安全拆分

不要直接删除整个 sandbox container。先逐层 `du`，本次确认 14 GB 全部位于：

`~/Library/Containers/com.oplus.devicespace.extension/Data/Library/Caches`

主要内容：

- `WeiXin`、`WeiXin（2）`、`WeiXin（3）`：约 12 GB
- 哈希设备目录下的 `WeiXin`：约 1.6 GB
- `Screenshots` 与 `Screenshots（2）`：约 882 MB

执行时只删除 `Data/Library/Caches`，保留：

- container 本体
- `Data/Library/Preferences`
- `Data/Library/HTTPStorages`
- O+ Connect 应用及登录项/后台服务

清理后 container 从约 14 GB 降至 3.1 MB，`oplus_remote_service` 仍在运行。

## 过期恢复暂存区

`hermes-trash-*` 是先前清理留下的恢复安全网，不应永久堆积：

1. 检查目录名日期和 `stat` 修改时间。
2. 超过既定 7 天观察期后，仍要等用户明确要求永久回收，或在其明确复制/点名该项时执行。
3. 删除前计量目录真实字节数；删除后确认路径不存在。

本次暂存区已超过 4 周，用户明确点名清理，因此永久删除合理。

## 执行模式

- 大目录删除使用 Python `shutil.rmtree`，避免带空格/全角括号路径和 shell `mv/rm` 的不稳定行为。
- 工具缓存优先使用工具自己的清理命令：`uv cache clean`、`npm cache clean --force`、`brew cleanup --prune=all -s`、`python -m pip cache purge`。
- 对应用缓存只删除已确认的 Cache 子树，不把 Application Support、数据库或登录态当缓存。

## 计量与验证

清理前按文件累计得到候选数据约 30.6 GB（十进制）。清理后：

- Data volume 可用空间从 240 GiB 增至 267 GiB
- `df -k` 计算实际可用空间增加 26.73 GiB
- O+ container 降至 3.1 MB
- uv/npm/brew/pip 命令仍可运行
- Hermes gateway、Hermes bridge、O+ 后台服务仍在运行

注意：候选文件字节总和与 APFS `df` 差值不会严格相等；最终报告同时给出“按路径统计的候选大小”和“Data volume 实际变化”，不要混用 GB/GiB。

## 可复用结论

- O+ Connect / realme 设备空间的大头若明确集中在 `Data/Library/Caches`，可以只清 Cache 子树，不需要删除整个  container。
- 先前为了可逆性建立的 `hermes-trash-*` 必须有观察期与最终回收步骤，否则“清理”只是搬家。
- 用户明确点名两个已审计条目并说“这些清理掉”，即构成对这两个范围的明确删除授权，无需再问一次。