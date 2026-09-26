# Session reference: rustfs robot-289 拷贝任务

会话日期:2026-08-17
机器:Ubuntu 26.04,GNOME Wayland,kk 用户
rclone:已装 v1.75.0(本以为要升级,实际已经是最新版;跑了 install 脚本,白白下了 30 MB 重装)
endpoint:`https://rustfs.gz.autolife.ai:8444`(自签证书,TLS verify fail = 20)
bucket:`robot-289`(在控制台 URL 里直接拿到),另外发现 `robot-shanghai-yuyu`

## 任务时间线

1. 用户在终端敲 `rclone copy rustfs:robot-289/...` → 报 "didn't find section in config file" → 求助
2. 我先看配置(目录在 `~/.config/rclone/`,空目录),探测 endpoint 通(403 + TLS=20,正常)
3. 用户给出 Web 控制台 URL,我从中推出 endpoint、bucket、TLS,缺 AK/SK
4. 用户多次表达"我不懂" → 我意识到他手头没 AK/SK → 引导他登 Web 控制台找 → 用户改主意,要求"先装 rclone,按官方文档走"
5. 我误判 rclone 是 1.60.1 旧版(实际是 1.75.0 最新),写了 install 脚本让他跑
6. 跑完发现版本没变,白白下了 30MB。诚实承认。
7. 用户给 AK/SK,写 `rclone.conf`,验证连通 → 21 个 bucket 可见
8. **关键错误**:我看到 `lsd rustfs:robot-289/2026-08-13` 只看了前 10 行,告诉用户"里面有 7-30~8-10 这 9 天"
9. 实际:有 12 个子目录,包括 8-11、8-12。`2026-08-13/`, `/14`, `/15`, `/16` 顶层目录**内容完全一致**(都是 7-30~8-12 12 天数据),只是不同时刻的归档快照
10. 用户改主意:只要 07-30~08-03。我准备跑时发现 8-16 下没有 2026-08-02 子目录(从 8-01 跳到 8-03,8-02 那天没数据)
11. 总大小 121 GiB,本机磁盘 409G 空闲,够。脚本写好放在 `/tmp/copy-289.sh`
12. 用户问 Windows 怎么上传 → 我给了 PowerShell 自下载 rclone + 上传脚本
13. 用户选方案 1(脚本)→ 打包 `rustfs-upload.zip`
14. 用户改目标桶为 `robot-shanghai-yuyu/290/`
15. 客户问另一台 Linux 怎么传 → 给 `setup-rustfs-upload.sh` self-contained 脚本
16. 用户问 Windows 怎么下载 → 加 `download-rustfs.ps1` + 重打包 zip

## 关键陷阱(已沉淀到 SKILL.md P1)

| 陷阱 | 现象 | 教训 |
|---|---|---|
| **lsd 看前 10 行** | 我只看了 `lsd` 的 head -10 就告诉用户"9 个子目录",实际 12 个 | 永远 `awk '{print $NF}'` 拿全;看全了再下结论 |
| **顶层日期≠采集日** | `2026-08-13/` 顶层目录里是 7-30~8-12 的采集数据 | 命名混淆很常见,先 lsd 一次摸清结构再说 |
| **跨日期快照重复** | 5 个顶层目录内容字节级一致 | 多 size 几次,一模一样的就别全拷 |
| **rclone size 返回 0B** | 子目录 size 报 0,但 lsd 看有内容 | 不可信,递归 ls 自己数 |
| **290 异常目录** | 桶名 robot-shanghai-yuyu 里有 sii_office/close_microwave_oven/ 这种明显错放的数据 | ls 顶层目测一下,有异常问用户再处理,别瞎删 |
| **rclone 已装但误判版本** | 我以为 1.60.1 旧版,跑 install 脚本下 30MB 重装同一个版本 | 装前 `rclone version` 看,最新版就不动 |

## 用户的"我自己来"信号

在多次出现以下信号时,应主动停下、不要再追加行动:
- "不用了我自己来" → 不要继续调优,问"还要别的吗"
- "不用管 不要动" → 异常数据/可疑情况别自作主张处理
- "给我命令就行" → 不需要解释原理,直接给命令

## 用户交付偏好(贯穿全程)

- **完整自包含脚本** > 分步说明
- **打包成 zip** 给一个文件 > 散落的多个文件
- **改最少的变量** 就能跑(3 个变量是上限,最好是 1-2 个)
- **进度条、断点续传** 是默认期望(给 `-P` 不用问)
- 跨平台:同一份 AK/SK 配出 Linux + Windows 都能用的脚本

## 后续可复用

- `/home/kk/rustfs-upload/` 下有 4 个文件:`rclone.conf`、`upload-rustfs.ps1`、`download-rustfs.ps1`、`setup-rustfs-upload.sh` + `/tmp/rustfs-upload.zip`
- 这些就是 templates/ 里的样板,直接用
- AK/SK 不写进 memory(虽然对当前会话有效),但避免跨会话泄露
