# CUA - Computer Use Agent 基础设施

> 仓库：https://github.com/trycua/cua ⭐15.5K
> 许可证：MIT
> 文档：https://cua.ai/docs

## 核心组件

### 1. Cua Driver（macOS 后台操作）
- **功能**：后台操控 macOS 原生应用，不抢焦点/光标/Space
- **协议**：MCP over stdio
- **支持**：Claude Code、Cursor、Codex、Gemini、OpenClaw 等
- **安装**：
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.sh)"
  ```
- **注册 MCP**：
  ```bash
  claude mcp add --transport stdio cua-driver -- cua-driver mcp
  ```
- **要求**：macOS 14 (Sonoma)+，Apple Silicon / Intel
- **三种捕获模式**：
  - `som`（默认）— AX 树 + 截图，适合元素索引点击
  - `ax` — 仅无障碍树，确定性元素寻址
  - `vision` — 仅截图，适合视觉模型

### 2. Cua Sandbox（跨平台沙箱）
- **功能**：统一 API 控制 Linux/macOS/Windows/Android 沙箱
- **安装**：`pip install cua`
- **支持**：
  - 云端（cua.ai）：Linux/Windows/macOS/Android
  - 本地（QEMU/Docker）：Linux/Windows/Android
  - 本地（Lume）：macOS

### 3. Cua Bot（协作式电脑操作）
- **功能**：给任意 agent 提供沙箱，窗口原生显示在桌面上
- **安装**：`npx cuabot`
- **使用**：
  ```bash
  cuabot claude      # Claude Code
  cuabot openclaw    # OpenClaw in sandbox
  cuabot chromium    # 浏览器
  ```

### 4. Cua Bench（基准测试）
- **功能**：评估电脑操作 agent，支持 OSWorld/ScreenSpot/Windows Arena
- **使用**：
  ```bash
  cd cua-bench
  uv tool install -e . && cb image create linux-docker
  cb run dataset datasets/cua-bench-basic --agent cua-agent
  ```

### 5. Lume（macOS 虚拟化）
- **功能**：Apple Silicon 上运行 macOS/Linux VM，近原生性能
- **安装**：
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/trycua/cua/main/libs/lume/scripts/install.sh)"
  ```
- **使用**：
  ```bash
  lume run macos-sequoia-vanilla:latest
  ```

## Python SDK 结构

```
libs/python/
├── agent/           # AI agent 框架
├── computer/        # 计算机交互 SDK
├── computer-server/ # 沙箱内驱动
├── core/            # 核心库
├── cua/             # 主包（pip install cua）
├── cua-auto/        # 自动化工具
├── cua-cli/         # CLI 工具
├── cua-sandbox/     # 沙箱 SDK
├── mcp-server/      # MCP 服务器
└── som/             # Set-of-Mark 标注
```

## 快速开始（本地 Docker）

```bash
# XFCE 轻量桌面
docker pull --platform=linux/amd64 trycua/cua-xfce:latest

# KASM 完整桌面
docker pull --platform=linux/amd64 trycua/cua-ubuntu:latest

# QEMU Windows 11
docker pull trycua/cua-qemu-windows:latest

# QEMU Android（无需准备 golden image）
docker pull trycua/cua-qemu-android:latest
```

## 与慧慧的集成潜力

- **Cua Driver** → 慧慧可以后台操控 macOS 应用（不抢主人焦点）
- **Cua Sandbox** → 安全执行自动化任务
- **Cua Bot** → 给慧慧一个可视化沙箱环境
- **Lume** → 在 MacBook Air 上运行隔离的 macOS/Linux 环境

---

_下载时间：2026-05-03_
_来源：trycua/cua ⭐15.5K_
