# references/uumit-v2-install-session.md — UUMit 2.x 装机真实 transcript

> 首次落地点：2026-08-15。主人给入口 `https://oss.uumit.com/skills/v2/index.json`，明确要求：全程大白话、不覆盖已有 memory/、先校验再解压。本笔记是第三人称视角的精简复盘，给未来同类装机 session 当 sample。

## 时间线

| 时点 | 动作 | 结果 |
|---|---|---|
| T0 | `mkdir -p /tmp/uumit-install && curl index.json` | 4587 字节 |
| T0+30s | `read_file /tmp/uumit-install/index.json` | 1 个 base + 6 ext，全 2.4.1 |
| T1 | `shasum` 验 bundle（160755B / `53ae26537f3507c54387b8b9316a197842111a515bece884c14d343f74e0d363`） | ✅ |
| T2 | `mktemp -d /tmp/uumit-staging-XXXXXX` + `unzip` | staging=gcwAfo；7 个子目录都在根 |
| T3 | staging `install.js --check` + `validate_skill.js` | 都 `ok:true / errors:[]` |
| T4 | 备 `tar /tmp/uumit-memory-backup-20260815-031421.tar`（15.8K，含 runtime + sessions + uumit-config.json） | ✅ |
| T5 | rsync 7 个包到 `~/.openclaw/skills/`，基座 `--exclude=memory` | ✅ |
| T6 | 正式目录再跑两道体检 | 都绿 |
| T7 | 正式目录 `node scripts/install.js`（不入 staging） | 返回 `verification_url: https://m.uumit.com/link` + `user_code: 8618B2BB` |
| T8 | `node scripts/auth.js --wait <device_code>` 后台跑（macOS 无 timeout → 用 `background=true, notify_on_complete=true`） | 等待主人浏览器确认 |

## 关键命令（直接复用）

```bash
# 下载 + 校验
curl -fsSL "https://oss.uumit.com/skills/v2/bundles/uumit-v2-53ae26537f3507c5.zip" -o bundle.zip
ACTUAL_SIZE=$(stat -f%z bundle.zip)
ACTUAL_SHA=$(shasum -a 256 bundle.zip | awk '{print $1}')
[ "$ACTUAL_SIZE" = "160755" ] && [ "$ACTUAL_SHA" = "53ae26537f3507c54387b8b9316a197842111a515bece884c14d343f74e0d363" ]

# staging 体检
STAGING=$(cat /tmp/uumit-install/staging_path.txt)
UUMIT_SKILL_DIR="$STAGING/uumit-agent" node $STAGING/uumit-agent/scripts/install.js --check
UUMIT_SKILL_DIR="$STAGING/uumit-agent" node $STAGING/uumit-agent/scripts/validate_skill.js

# 正式目录 rsync（基座 memory/ 跳过）
for skill in uumit-agent uumit-cruise uumit-realtime uumit-recommend uumit-publisher uumit-compute uumit-social; do
  mkdir -p ~/.openclaw/skills/$skill
  [ "$skill" = "uumit-agent" ] && rsync -a --exclude=memory $STAGING/$skill/ ~/.openclaw/skills/$skill/ \
                              || rsync -a $STAGING/$skill/ ~/.openclaw/skills/$skill/
done

# 正式目录复核（同样的两道体检，路径换成正式目录）

# 设备授权
UUMIT_SKILL_DIR=/Users/kk/.openclaw/skills/uumit-agent \
  node /Users/kk/.openclaw/skills/uumit-agent/scripts/install.js
# → verification_url + user_code
```

## 踩过的具体小坑

1. **`timeout` 命令在 macOS 没装**（gnu coreutils 不默认装）。
   - 现象：shell 报 `timeout: command not found`
   - 解法：直接用 `terminal(background=true, notify_on_complete=true)` 让 Hermes 框架接管超时和通知
2. **rsync 比 cp -r 在 macOS 上更稳**：碰到资源叉/隐藏文件不踩坑
3. **install.js 既出 device_code 又指明 required_next_command**：要原样复用 device_code，不要自己重抽

## 元数据（这次装机）

| 字段 | 值 |
|---|---|
| 入口 | `https://oss.uumit.com/skills/v2/index.json` |
| bundle | `uumit-v2-53ae26537f3507c5.zip` |
| bundle 大小 | 160,755 bytes |
| bundle sha256 | `53ae26537f3507c54387b8b9316a197842111a515bece884c14d343f74e0d363` |
| 基座 | `uumit-agent` v2.4.1 |
| 扩展 | `uumit-cruise / -realtime / -recommend / -publisher / -compute / -social` |
| 正式目录 | `/Users/kk/.openclaw/skills` |
| 内存备份 | `/tmp/uumit-memory-backup-20260815-031421.tar`（15.8K） |
| 授权入口 | https://m.uumit.com/link |
| 用户码 | 8618B2BB |
| device_code | `rgGNyLVN6U_PfOFkH52MELEsIHKUSgniAT1aQjsIk8o` |

## 给未来同类 session 的注意事项

- 主人特爱 emoji🌸✨，装机提示里加上很合他的胃口
- 主人不爱反问"选档"——授权后台化不要等他拍板
- 主人 ABSOLUTE 模式下，基座 memory/ 跳过 = 默认档；不要请示"要不要保留 memory"
- 装机完成后 Onboarding 别急着念——等他二次确认授权结果再念
- 这个脚本产生的 `staging_path.txt` / `bundle.zip` 留在 `/tmp` 就行，重启清掉，不会污染
