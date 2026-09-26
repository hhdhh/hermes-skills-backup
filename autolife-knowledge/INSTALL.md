# 安装说明

三步，大约两分钟。

## 1. 放入 skill 目录

把整个 `autolife-knowledge` 文件夹放到：

```
~/.workbuddy-ai/skills/autolife-knowledge
```

Windows 上是 `C:\Users\<你的用户名>\.workbuddy-ai\skills\autolife-knowledge`。

## 2. 配置密钥

打开终端，进入 skill 的 `scripts` 目录：

```bash
cd ~/.workbuddy-ai/skills/autolife-knowledge/scripts
python setup.py
```

脚本会提示你粘贴**管理员分发的 API 密钥**（以 `kb_` 开头）。

> 粘贴时屏幕上不会显示字符，这是正常的。粘贴后直接回车。

脚本会立刻拿这个密钥去打一次真实检索来验证：

- 密钥正确 → 提示「校验通过」，写入配置
- 密钥错误或被吊销 → 提示「API 密钥无效或已被吊销（HTTP 401）」
- 网关不通 → 提示具体原因

**不需要 VPN、不需要额外账号。**

## 3. 开始使用

```bash
python retrieve_kb.py "机器人视觉无法启动"
```

在 WorkBuddy 里直接用自然语言提问即可，比如：

> 机器人启动后检测不到路由器 wifi，怎么排查？

---

## 常见问题

**Q：怎么换密钥？**

```bash
python setup.py --force
```

**Q：怎么确认现在配置是否正常？**

```bash
python setup.py --check
```

**Q：提示 401？**

密钥无效或已被吊销。找管理员确认，或要一把新的。

**Q：提示 404？**

网关地址不对。检查 `.env` 里的 `KB_PUBLIC_URL` 是否为
`https://fae.gz.autolife.ai:8866/kb`。

**Q：提示连接超时？**

网络不通。确认这台机器能访问 `fae.gz.autolife.ai:8866`。

**Q：密钥会存在哪里？**

skill 根目录的 `.env` 文件，已加入 `.gitignore`，不会被提交。
请不要把它发给别人。

---

## 环境要求

- Python 3.8 或更高
- 无需安装任何第三方库（只用标准库）
