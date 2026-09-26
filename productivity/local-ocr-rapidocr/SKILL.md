---
name: local-ocr-rapidocr
description: Use when 主人发图片要提取文字、设备铭牌/现场照片/截图识别，要求不联网不出网。
metadata:
  triggers:
    - "识别文字"
    - "OCR"
    - "图片提取"
---

# 本地 OCR（RapidOCR）

> 完整描述：本机离线 OCR（RapidOCR + PP-OCRv4，中文满分置信度）。Use when 主人发图片要提取文字、设备铭牌/现场照片/截图识别，要求不联网不出网。

## 环境（已验证可用）

- venv：`~/.hermes/workspace/feishu-ocr-venv/`（Python 3.11）
- 引擎：rapidocr_onnxruntime + onnxruntime（PP-OCRv4 det/cls/rec 三模型内置，无需下载）
- 实测：英文 0.98 / 中文 1.00 置信度，单图 1.3-1.7s

## 用法

```bash
~/.hermes/workspace/feishu-ocr-venv/bin/python -c "
from rapidocr_onnxruntime import RapidOCR
result, _ = RapidOCR()('/path/to/img.png')
for line in (result or []): print(line[1], line[2])   # 文本, 置信度
"
```

图片无中文路径问题可先 `from PIL import Image` 转存 /tmp。批量场景参考 `~/.hermes/knowledge/feishu-study/ocr_local.py`（历史飞书图片归档脚本）。

## 坑

- 系统 Python 无此包，必须用 venv 解释器；uv 缓存里的副本是残留不可用。
- 纯环境问题（未装包/路径错）报 ModuleNotFoundError 时先查解释器路径，别重装。
