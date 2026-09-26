---
name: local-ocr
description: Use when 需要读取图片里的文字（截图/照片/文档扫描）且不能或不便联网时。
---

# 本地 OCR（RapidOCR / PP-OCRv4）

> 完整描述：本地图片 OCR 文字识别。Use when 需要读取图片里的文字（截图/照片/文档扫描）且不能或不便联网时。RapidOCR 纯离线，命令 `ocr <图片>` 一行出结果。

## 快速使用

```bash
ocr <图片路径>          # 按行输出识别文本
ocr <图片> --json       # JSON：text + conf + box 坐标
ocr <图1> <图2> ...     # 多图共一次模型加载，更快
```

命令位置 `~/.local/bin/ocr`，shebang 直指 `~/.hermes/workspace/feishu-ocr-venv/bin/python`，无需激活 venv。

## 引擎与模型

- 引擎：RapidOCR（ONNX Runtime CPU 推理，纯本地，不联网）
- venv：`~/.hermes/workspace/feishu-ocr-venv/`
- 模型（PP-OCRv4 系列，随包内置）：det（检测）→ cls（方向分类）→ rec（识别）三段流水线
- 中文 / 英文 / 数字 / 中英混排均可；单图约 1.4s（含 1s 模型加载）

## 识别质量基准（2026-09-13 实测）

| 类型 | 输入 | 输出 | 评价 |
|---|---|---|---|
| 中文 | 灰灰的本地 OCR 测试 | 灰灰的本地OCR测试 | 全对（空格被吞属正常） |
| 英文数字 | AUTO LIFE 2026 Robot Test 12345 | AUTOLIFE2026RobotTest12345 | 字符全对，空格丢失 |
| 淇?混排 | 故障代码 E-1103 / IP: 192.168.65.66 | 原样识别 | 全对 |

坑：
- 英文短语内空格会丢失（PP-OCR rec 特性），需要分词时用 `--json` 拿 box 分行重建
- 置信度 conf < 0.8 的行要人工复核
- 旋转图会先过 cls 方向分类自动纠正

## 典型场景

- 机器人现场照片读故障码/序列号/铭牌（FAE 日常）
- 截图里的报错信息提取
- 扫描件/PDF 页转文字（先转 PNG 再 ocr）

## 维护

- 升级：`~/.hermes/workspace/feishu-ocr-venv/bin/pip install -U rapidocr-onnxruntime`
- 命令源码：`~/.local/bin/ocr`（20 行，可按需加 flag）
