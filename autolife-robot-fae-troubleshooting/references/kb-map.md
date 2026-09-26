# 内部知识库检索地图（Autolife FAE）

根目录：`/home/kk/.hermes/knowledge/`。先按故障类定位文档再读，不全文载入。

## 故障类 → 首选文档

| 故障类 | 文档 | 内容 |
|---|---|---|
| 不抓取/识别/抓偏 | `feishu-study/reviews/UjMVdukoroVMSUxffjPcxno0nMg.md` | 太空舱饮品零食配置流程（AI/GV 双环境、部署、路点、订单链路） |
| | `feishu-study/reviews/Xwrbd5RzqooEOSxeGltcQvOBnR0.md` | 维护培训：dataset/XML/blackboard 参数传递与生效规则 |
| | `feishu-study/reviews/ElQTdKdXNoqPAAxJ2pwcjjjGnTe.md` | 场景流程故障边界（分型归因） |
| | `feishu-study/reviews/FzeidXu9SoxyKHxtJvMccwsinHc.md` | 咖啡冰淇淋配置 + 现场答疑（取杯器/咖啡机适配） |
| 电量/电池 | `feishu-study/reviews/LZa6wcOrkijhbLkTJuDcGqIRnSd.md` | 现场常见问题处理指南（电量异常 v2→v1、雷达接反、连接切换） |
| | `wiki/robot-install-manual-deep-analysis-2026-08-10.md` | 装机手册深读（电池模块未找到 → v2；各模块检测前置） |
| 服务架构/健康 | `feishu-study/reviews/WIRywXmHki2JlPkeUeJceNUlnGf.md` | 服务关系：flow/arm/gv-control/gv-slam/vision/ai-grasp/face |
| 现场命令/故障表 | `feishu-study/attachments/Tr4cbkdNWoAa21xP4o7c0TgfnDf.md` | 常见故障排查表、机械臂限幅、异常处理、赛前检查清单 |
| 装机/检测 | `wiki/manuals/autolife-s2/` | S2 装机与系统配置手册解读 |

## 检索技巧
- 中文关键词用 `|` 交替组（如 `抓取失败|不抓取|抓不到`、`电量|电池|BMS|SOC`、`driver_version`），带 `file_glob: *.md`。
- 先窄后宽：第一轮太散（`total_count_is_lower_bound`）就换更具体的词或加 `path` 限定到 `reviews/`。
- 命中后用 read_file 带 offset 分页读上下文，不整读大文件。
- `feishu-study/reviews/` 里的笔记带原文 block ID 可回溯飞书原文。
- 精读笔记常把"原文待验证项"标出来——引用时保留这些限定语，不要把建议写成已验证事实。
