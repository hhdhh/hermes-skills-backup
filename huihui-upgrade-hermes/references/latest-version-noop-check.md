# “更新到最新版”时的 no-op 判定

适用于用户未指定目标版本，只要求“更新到最新版本”的场景。

## 关键判定

`uv pip install --upgrade hermes-agent --dry-run` 可能只列出 transitive dependencies 的升级，例如 Starlette、Uvicorn、AnyIO 等，而完全没有 `hermes-agent` 本身的版本变化。

这不代表 Hermes 有新版。判断规则：

1. 记录当前版本：`hermes --version` 与 `python -m pip show hermes-agent`。
2. 执行 upgrade dry-run。
3. 只有 dry-run 计划中出现 `hermes-agent OLD -> NEW`，且 NEW 高于当前版本，才进入备份和安装步骤。
4. 若计划中只有依赖变化，判定 Hermes 已是最新版；不要为了“看起来执行了升级”而更新无关依赖。
5. Hermes Web UI 是独立 npm 包，另行比较：
   - 已安装：`npm list -g hermes-web-ui --depth=0`
   - 最新版：`npm view hermes-web-ui version`
6. no-op 也要做健康验证：Hermes import、Web UI HTTP 200、gateway 状态、skill 数量。

## 为什么要保守

依赖单独升级可能带来兼容性风险，尤其是 FastAPI/Starlette/Uvicorn 栈。用户要求“把 Hermes 更新到最新版”不等于授权更新所有可更新的 Python 依赖。目标包已最新时，正确结果是明确报告 no-op，而不是制造无必要变更。

## 报告模板

- Hermes Agent：当前版本 = 最新版本
- Hermes Web UI：当前版本 = 最新版本（若已安装）
- 运行健康：CLI/import、Web UI、gateway、skills 均通过
- 未执行无关依赖升级：避免引入兼容性风险
