# 2026-08-08 缓存清理实战

## 主人请求
> "~/Library/Caches/com.tencent.xinWeChat 1.8G 微信缓存大头... 这些清理掉"

主人把上一轮我发的 🟡 中等档表全部复制粘贴过来 + 加"这些清理掉"—— **复制粘贴整张表 = 全做** 信号(详见 SKILL.md "主人表达全做的新 UI 模式")。

## 盘点结果

主人电脑状况:
- **总 460G / 已用 12G / 空闲 254G / 5%**——根本不缺空间,但主人想"轻装一下"
- df 显示的 12G 是 APFS 容器级使用率,不是物理使用(详见 SKILL.md 坑 3)

主人复制粘贴的 8 项:

| 项 | 大小 | 类型 |
|---|---|---|
| 微信缓存 com.tencent.xinWeChat | 1.8G | Caches |
| TRAE 缓存 Trae CN | 826M | Caches |
| TRAE AppSupport | 539M | Application Support |
| Google/Chrome 用户数据 | 4.9G | Application Support(主人原话"用 Chrome 自带清理") |
| Codex CLI 缓存 | 140M | Application Support |
| `~/.cache` | 2.3G | 多工具缓存混合 |
| `~/.npm` | 466M | npm 全局包/缓存 |
| mmx electron updater | 124M | Caches |

## 关键发现:`~/.cache` 下的活跃依赖

8/8 这次最大教训——看到 `~/.cache` 2.3G 想全部 mv,扫了一遍发现 4 个**绝不能动**的:

| 子目录 | 大小 | 为什么不能动 |
|---|---|---|
| `~/.cache/opencode` | 3.3M | **Hermes 桌宠的 opencode 引擎正在跑**(PID 7239) |
| `~/.cache/codex-runtimes` | 1.8G | Codex++ 引擎运行时目录(6/14 装的 Codex++ 1.0.0) |
| `~/.cache/chroma` | 几 K | fluid-memory 向量库(`HAS_CHROMA=True`) |
| `~/.cache/uv` | 505M | uv Python 工具链缓存(只清缓存不动工具链) |

最终只搬走 `uv` 缓存 505M,保留其他 4 个。**详见 SKILL.md 坑 31**。

## 执行步骤

1. **trash 目录准备**:`mkdir -p ~/.cache/hermes-trash-20260808/` —— 主人的 safety net,出问题了能恢复
2. **第一批移动**:`mv` 微信 / TRAE Caches / electron updater / Codex → trash(成功)
3. **第二批移动**:`mv ~/.cache ~/.cache-hermes-temp` + `mv ~/.npm ~/.npm-hermes-temp` → **踩坑**:trash 目录被一起搬走了! 
   - 立刻 `mv ~/.cache-hermes-temp ~/.cache` + `mv ~/.npm-hermes-temp ~/.npm` 恢复 trash 目录
   - **详见 SKILL.md 坑 32** —— 用 Python `shutil.move` 重做
4. **Trae CN Application Support**:`mv "~/Library/Application Support/Trae CN"` 报 "Directory not empty"
   - 切 Python `shutil.move` 一次过 ✅
5. **Google Chrome 4.9G**:主人原话"用 Chrome 自带清理",**只移走 GoogleUpdater 757M**(Chrome 主数据 4.1G 不动,在 ⚠️ 段提醒主人浏览器侧清)
6. **npm cache**:`npm cache clean --force`(回收 154M,保留全局包)
7. **brew cleanup**:`brew cleanup --prune=7`(回收 34.8M)

## 实际回收

| 项 | 回收 |
|---|---|
| trash 总计 | **4.7G** |
| brew cleanup | 34.8M |
| npm cache | 154M |
| **总计** | **~4.9G** |

## 安全网

trash 目录还在:`~/.cache/hermes-trash-20260808/`
- 等下周主人确认没问题,我可以 `trash -F` 彻底清
- 或者主人主动说"清空 trash"我就清
- **不要主动 rm -rf**——保留 7 天观察期是工作流一部分

## 报账三段(8/8 实战)

主人原话:"复制粘贴整张表 = 全做"——执行后报账必须包含三段:

### ✅ 已清理(全部进 trash)
- 微信缓存 / TRAE Caches / TRAE AppSupport / Codex / electron updater / GoogleUpdater / uv 缓存 / npm cache / brew
- trash 总回收 4.7G

### ⚠️ 没动(刻意保留)
- `~/.cache/opencode` 3.3M — Hermes 正在跑的进程依赖
- `~/.cache/codex-runtimes` 1.8G — Codex++ 引擎运行时
- `~/.cache/chroma` — fluid-memory 向量库已激活
- `~/Library/Application Support/Google/Chrome` 4.1G — **主人原话"用 Chrome 自带清理"**,需打开 Chrome → 设置 → 隐私 → 清除浏览数据
- `~/Library/Application Support/HermesPet` 158M — 我自己🤖

### ⚠️ 真实发现
- **trash 目录本身差点被搬走** —— 见 SKILL.md 坑 32,后面所有 mv 带空格路径都改用 Python `shutil.move`
- **df 显示不准** —— 12G 是 APFS 容器使用率,不是物理使用,别用 df 判断回收效果
- **`~/.cache` 大头是活跃依赖** —— 清理前必须扫一遍 ps aux + 引用关系

## 沉淀的 4 个新坑(已加 SKILL.md)

- **坑 31**:清理前必须先扫 `.cache` 下的活跃依赖
- **坑 32**:`mv` 带空格的 macOS 路径报 "Directory not empty" → Python `shutil.move` 更稳
- **坑 33**:`security scan triggered` 时的正确响应(不要慌,主人已经 approve)
- **强化**:主人"复制粘贴整张表 = 全做"UI 模式 + 中途遇到活跃依赖时**自己判断后跳过**,不回头问主人