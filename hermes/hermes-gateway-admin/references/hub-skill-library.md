# hermes 化身 skill 库（class-level umbrellas）

> 2026-07-04 灰灰立 · 主人 7/4 全权下放后立的两个 class skill。

## hermes 目录布局

```
~/.hermes/skills/hermes/
├── hermes-gateway-admin/         # 平台层 admin
│   ├── SKILL.md
│   ├── references/
│   │   ├── launchd-bootstrap-einval.md
│   │   └── crontab-layout.md
│   ├── templates/
│   │   └── profile-plist.template.plist
│   └── scripts/
│       └── version-watchdog.sh
└── skill-readiness-audit/         # skill 栈验收
    ├── SKILL.md
    ├── templates/
    │   └── report.template.md
    └── scripts/
        └── audit.sh
```

## 两个 class skill 各自管什么

### `hermes-gateway-admin`
管 Hermes 引擎本身（`~/.hermes/profiles/*` / launchd / plist / npm / crontab）。
触发词: gateway / plist / LaunchAgent / launchctl / profile install / hermes version / web-ui update / "Bootstrap failed"

### `skill-readiness-audit`
管 skill 栈本身（`SKILL.md` 存在 / 依赖齐 / import 通 / smoke test）。
触发词: 检查技能 / 技能 OK 吗 / skill audit / verify my skills / 依赖齐不齐 / check skill / skill broken / missing dependency

**两个 skill 不重叠**——`hermes-gateway-admin` 是平台层,`skill-readiness-audit` 是 skill 层。

## 7/4 实测

- `hermes-gateway-admin` 立完立即被主人下个任务触发（启 5 个空 profile gateway）—— 立后用一次
- `skill-readiness-audit` 立完立即被主人下个任务触发（检查技能是否完全 OK）—— 立后用一次
- 2/2 都立得有用,**不是空立**

## 升级检查（下次复审）

- [ ] `hermes-gateway-admin` 是不是漏了 hermes-studio-mcp 单独升级路径（当前只覆盖 hermes-web-ui main package）
- [ ] `skill-readiness-audit` 是不是需要加 `yq` 解析 frontmatter（当前用 grep 简化）
- [ ] `skill-readiness-audit` 是不是要把 empty skill 报账拆出来（和 broken 分两段）
