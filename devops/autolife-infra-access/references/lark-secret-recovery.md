# lark-cli App Secret 轮换自愈（Linux）

When every lark-cli call fails with `The client secret is invalid`, the App Secret was rotated on the server. Fix it in place — no reinstall, no re-bind needed.

## Storage scheme

- Key material: `~/.local/share/lark-cli/master.key` (32 raw bytes)
- Secret file: `~/.local/share/lark-cli/appsecret_<appid>.enc` — despite config.json's `"source": "keychain"`, on Linux this local file IS the keychain
- Cipher: AES-256-GCM, key = master.key **raw bytes**, file layout = `nonce(12) || ciphertext || tag(16)`

## 1. Decrypt the current secret

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
mk  = open("~/.local/share/lark-cli/master.key", 'rb').read()   # expanduser first
enc = open("~/.local/share/lark-cli/appsecret_<appid>.enc", 'rb').read()
secret = AESGCM(mk).decrypt(enc[:12], enc[12:], None).decode()
```

If `AESGCM(mk)` fails the tag check, try `hashlib.sha256(mk).digest()` as the key — derivation has varied across CLI builds. Never print the full secret; check length/prefix only.

## 2. Verify server-side before touching anything

```bash
curl -s https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal \
  -d "app_id=<appid>&app_secret=<secret>"
# code 0    -> secret valid, problem is elsewhere (token refresh path)
# code 10014 "app secret invalid" -> rotated; need the new one from the app admin
```

A fresh secret comes from the open-platform console (open.feishu.cn/app → the app → 凭证与基础信息) — only an app admin can see it.

## 3. Re-encrypt the new secret (backup first)

```python
import os, shutil
shutil.copy(enc_path, enc_path + '.bak')
nonce = os.urandom(12)
open(enc_path, 'wb').write(nonce + AESGCM(mk).encrypt(nonce, new_secret.encode(), None))
```

Do NOT edit `~/.lark-cli/<workspace>/config.json` — its `appSecret: {source, id}` pointer stays valid.

## 4. Re-run the device flow

`lark-cli auth login --recommend --no-wait --json` now succeeds; hand the verification_url to the user (or complete via browser automation — Casdoor page is React-rendered; click `.provider-link` then the 「授权」 button, wait for "Login Successful"), then finish with `--device-code`. Verify with a cheap API call (`api GET /open-apis/drive/explorer/v2/root_folder/meta`).
