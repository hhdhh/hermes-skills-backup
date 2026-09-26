---
name: rustfs-rclone-helper
description: Use when uploading, downloading, syncing, or scripting rc...
---

# rclone ↔ rustfs 工作流

> 完整描述：rclone ↔ rustfs (S3-compatible object storage) workflows. Use when uploading, downloading, syncing, or scripting rclone against rustfs endpoints with self-signed certs.

## 关键事实(2026-08-17 建立)

- **rustfs endpoint**: `https://rustfs.gz.autolife.ai:8444` (autolife 内部,GZ 节点,自签证书)
- **类型**: S3 兼容,`provider = Other`,**必须** `force_path_style = true`
- **常用桶**: `robot-001` `robot-234` `robot-239` `robot-248`...`robot-289`, `robot-shanghai-yuyu`, `autolife-data-upload-test`, `apt`, `parseable`, `fae-tools` 等
- **AK/SK**: 已配到用户 `~/.config/rclone/rclone.conf`,**含 secret_access_key,等同于 rustfs 完整控制权**

## 标准 rclone.conf

```ini
[rustfs]
type = s3
provider = Other
env_auth = false
access_key_id = ab5OdfRfpKPBlEdWggee
secret_access_key = Gu6duziYfjO6Z2ckF50W5jS8u9daKrnMu70J9meM
endpoint = https://rustfs.gz.autolife.ai:8444
force_path_style = true
```

## 命令模板

**上传(本地 → rustfs)**
```bash
rclone copy "$LOCAL" "rustfs:$BUCKET/$PREFIX/" -P \
  --no-check-certificate --retries 10 --retries-sleep 5s --transfers 8
```

**下载(rustfs → 本地)**
```bash
rclone copy "rustfs:$BUCKET/$PREFIX/" "$LOCAL" -P \
  --no-check-certificate --retries 10 --retries-sleep 5s --transfers 8
```

**只看不传**
```bash
rclone lsd rustfs:                              # 列 bucket
rclone lsd rustfs:$BUCKET --no-check-certificate  # 列子目录
rclone size "rustfs:$BUCKET/$PREFIX" --no-check-certificate  # 大小+文件数
```

## ⚠️ 坑(2026-08-17 验证)

1. **`--no-check-certificate` 必须**(自签证书),Win 端 rclone.conf 里加 `no_check_certificate = true`,命令行也加
2. **路径有空格用引号**:`"/home/kk/289 2026-08-16"`,Linux 下 `cd` 到空格目录会失败,直接传完整带空格路径最稳
3. **顶层日期 = 归档日,不是采集日**:`robot-289/2026-08-13/` 实际是 7-30~8-12 多日合集,不是 8-13 单天;拷之前用 `lsd` 看清楚
4. **同名顶层目录内容常重复**:8-13/8-14/8-15/8-16 内容完全一样,挑一份拷,别多份占空间
5. **桶内可能混垃圾数据**:`robot-shanghai-yuyu/290/` 里有 sii_office 任务数据(看着像别人误传),`copy` 不会删但用户可能误以为是机器人数据
6. **PowerShell 脚本必须 0 中文字符**(见 `hermes-agent-skill-authoring`/memory 的编码坑)

## 多平台脚本规范

- **Linux**: 直接 rclone 命令,无需脚本(rclone v1.75.0 已装,conf 已配)
- **Windows**: PowerShell 自下载 rclone.exe + 复用 conf,`-Mode upload/download` 二合一参数化
- **打包位置**:`~/rustfs-upload/` + `/tmp/rustfs-upload.zip`

## 完整脚本(Win 端 + Linux 端)在

- `/home/kk/rustfs-upload/rustfs.ps1` (Win 合一版,纯英文)
- `/home/kk/rustfs-upload/setup-rustfs-upload.sh` (Linux 一键)
- `/home/kk/rustfs-upload/rclone.conf`
- `/home/kk/rustfs-upload/README.md`
- zip: `/tmp/rustfs-upload.zip`
