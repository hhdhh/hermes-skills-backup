# 对话栈外接工具复刻配方（robot_tools 模式）

适用：给 vision 内置 AIChatbotManager 加查询/识别类能力（看一眼、查周边、点单），不建独立服务、不动 .so/音色/人设。

## 四步部署

1. `robot_tools/<name>.py`：TOOL_SCHEMA（扁平：type/name/description/parameters 顶层）+ `run(arguments: dict, ai_mgr=None)`。参考同目录 base_tool.py。
2. `robot_tools/__init__.py` ENABLED_TOOLS 加一行 `"<name>",`（sed 插在稳定锚点行后）。
3. `assets/prompt/prompt.txt` 工具规则区插触发段：何时调 / 参数填什么 / 禁过程汇报话术（返回后直接说答案）/ 看不清或失败的兜底话。
4. `systemctl --user restart face-detection-service && sleep 12 && systemctl --user restart vision-service`（vision 重启必连带 face）。

## 验证（三道枚不是服务 active）

- `journalctl --user -u vision-service | grep "Loaded external tool schema"` 点名新工具在列；
- `grep -c` 计数 = ENABLED_TOOLS 长度（N-1 = schema 结构不对）；
- 远端单测：sys.path 注入 site-packages 后 importlib 导入模块，跑 `run({...})` 看真实返回。

## 失败兜底
- schema 写成 OpenAI 嵌套式（function.name）→ 加载器静默跳过，无报错。唯一症状：日志 schema 列表少一个。
- 远端多行命令用 base64 传输：`echo <b64> | base64 -d > /tmp/x.py && python /tmp/x.py`。
- API key 从 settings.toml 用宽松 regex 取：`QWEN_API_KEY\s*=\s*["\']([^"\']+)`（严格行匹配会漏）。

## 回滚

所有改动点先 `cp <file> <file>.bak.<功能>-<日期>`；回滚 = bak 覆盖回 + 联动重启 + 日志锚点复验。
