---
name: lark-cli-secret-recovery
description: Use when lark-cli 报 client secret is invalid / app secret...
version: 1
author: hermes-agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [lark-cli, feishu, app-secret, oauth, troubleshooting]
---

# lark-cli App Secret 失效排查（Linux）

> 完整描述：Use when lark-cli 报 client secret is invalid / app secret invalid (10014) 或用户要求用户令牌重新授权。定位 secret 存储并验证是否真失效，再走重授权流程。

症状：`lark-cli auth status` 显示 user identity `needs_refresh`，但实际调用报 `The client secret is invalid`，且 `auth login` 发起设备授权也被拒。此时刷新令牌链路已断，必须先修 Secret。

## 排查流程（按序）

1. **区分 Secret 失效 vs 令牌过期**：令牌过期时 `auth login --recommend --no-wait --json` 能正常返回 verification_url；如果连设备授权都报 `client secret is invalid`，是 Secret 本身被服务端作废，直接进第 2 步。
2. **定位 Secret 存储**（Linux 无 macOS Keychain，配置里写的 `source: keychain` 实际落在本地加密文件）：
   - 配置：`~/.lark-cli/<workspace>/config.json`（`appSecret.id` 形如 `appsecret:<app_id>`）
   - 密文：`~/.local/share/lark-cli/appsecret_<app_id>.enc`（60 字节 = 12B nonce + 密文含 16B GCM tag）
   - 主密钥：`~/.local/share/lark-cli/master.key`（32 字节，直接作 AES-256-GCM key）
3. **解密验证**（只看长度/前缀，不打印全文）：

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
mk = open('/home/kk/.local/share/lark-cli/master.key','rb').read()
enc = open('/home/kk/.local/share/lark-cli/appsecret_<app_id>.enc','rb').read()
secret = AESGCM(mk).decrypt(enc[:12], enc[12:], None).decode()  # 32 字符
```

4. **权威验证 Secret 是否真失效**：拿 appId+secret 直接打飞书内部接口，返回 code 10014 即服务端已作废，与 CLI 无关：

```python
import urllib.request, urllib.parse, json
data = urllib.parse.urlencode({'app_id': APP_ID, 'app_secret': secret}).encode()
req = urllib.request.Request('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', data=data)
print(json.loads(urllib.request.urlopen(req, timeout=10).read()))
```

5. **修复路径**：管理员去 https://open.feishu.cn/app/<app_id> → 凭证与基础信息 → 取最新 Secret → `lark-cli config secret --app-id <app_id>`（或把新 Secret 交给 agent）→ 重跑 `lark-cli auth login --recommend --no-wait --json`，把 verification_url 原样发给用户，等确认后 `lark-cli auth login --device-code <code>` 收尾。

## Pitfalls

- 别在 `auth status` 正常后就停：user identity 显示 `available: true` 但 token 实际已清，只有真调 API 才暴露。诊断必须以一次真实 API 调用为准。
- 别反复重试 `auth login`：Secret 无效时重试无意义，只会刷同样错误。先走第 4 步验证。
- `config.json` 顶层没有明文 appId/appSecret（在 `apps[0]` 里且 Secret 只存 keychain 引用），grep 配置文件找不到 Secret 是正常的，去 `~/.local/share/lark-cli/` 找。
- 解密失败先试 `master.key` 直接作 key（不要先套 sha256）——实测该格式就是原始 32B key + nonce 前置。
- 报错时 CLI 尾部附带的 update 提示（1.0.x 可升级）与故障无关，不要被带偏去先升级。
