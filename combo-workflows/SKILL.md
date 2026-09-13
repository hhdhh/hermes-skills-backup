---
name: combo-workflows
version: 1.0.0
description: "方案4主动学习循环：proactive-agent + multi-search-engine + self-improving + delegate-task 无缝联动"
---

# 方案4：主动学习循环 🌀

**核心组合：** `proactive-agent` + `multi-search-engine` + `self-improving` + `delegate-task`

---

## 工作流架构

```
proactive-agent (主动发现需求)
         ↓
  multi-search-engine (自主调研)
         ↓
     self-improving (记录教训)
         ↓
    delegate-task (并行验证)
         ↓
   结果汇报 + 更新记忆
```

---

## 触发条件

当主人说这些关键词时，自动启动对应子工作流：

| 触发词 | 子工作流 |
|--------|---------|
| "研究"、"调研"、"了解一下" | 主动调研流 |
| "帮我看看"、"为什么"、"怎么回事" | 问题排查流 |
| "有什么方法"、"怎么搞定" | 方案探索流 |
| "你觉得"、"建议" | 深度分析流 |

---

## 子工作流详解

### 1. 主动调研流

**触发：** 主人提到需要了解某主题

**步骤：**
```
1. proactive-agent 分析需求，确定调研深度
2. multi-search-engine 并行搜索（中英文+多引擎）
3. self-improving 记录关键发现到 memory.md
4. delegate-task 并行验证信息准确性
5. 生成调研报告，主动汇报
```

**输出格式：**
```markdown
# 调研报告：{主题}
## 核心发现
- 发现1
- 发现2
## 来源验证
- [验证中/已验证]
## 下一步建议
```

---

### 2. 问题排查流

**触发：** 主人说"帮我看看为什么..."

**步骤：**
```
1. proactive-agent 分析问题特征
2. multi-search-engine 搜索类似问题
3. self-improving 记录错误模式
4. delegate-task 并行尝试多种解决方案
5. 验证后汇报最优解
```

**输出格式：**
```markdown
# 问题诊断：{问题描述}
## 可能原因
1. 原因A
2. 原因B
## 验证结果
- 方案A：成功/失败
- 方案B：成功/失败
## 推荐方案
```

---

### 3. 方案探索流

**触发：** 主人问"怎么搞定XXX"

**步骤：**
```
1. proactive-agent 拆解任务为子步骤
2. multi-search-engine 搜索多种方案
3. self-improving 记录有效方案
4. delegate-task 并行测试不同方案
5. 对比评估，输出最佳路径
```

**输出格式：**
```markdown
# 方案对比：{任务}
## 方案A
- 优点：
- 缺点：
- 验证结果：
## 方案B
- 优点：
- 缺点：
- 验证结果：
## 推荐：方案X
```

---

### 4. 深度分析流

**触发：** 主人说"你觉得..."

**步骤：**
```
1. proactive-agent 主动搜索相关案例
2. multi-search-engine 获取多角度信息
3. self-improving 关联历史经验
4. 生成有深度的分析建议
```

---

## 关键协同规则

### WAL + Self-Improving 联动
- 每次搜索前：WAL 记录当前问题/需求
- 每次搜索后：立即提炼关键发现
- 任务完成：self-improving 记录最终结论

### Delegate-Task 任务分配
```
主任务：调研 {主题}
├─ 子任务1：搜索中文资料
├─ 子任务2：搜索英文资料
├─ 子任务3：验证信息准确性
└─ 子任务4：整理报告
```

### Self-Improving 记忆触发
- 搜索时发现新线索 → 记录到 projects/当前项目.md
- 排查问题有新发现 → 记录到 corrections.md
- 完成复杂任务 → self-reflection 格式记录

---

## 使用示例

**主人说：** "研究一下怎么用 AI 自动化我的文档处理流程"

**我的执行：**

1. **主动分析** (proactive-agent)
   - 这是一个"调研+方案探索"复合任务
   - 深度：中高级，需要具体工具推荐

2. **并行搜索** (multi-search-engine)
   - 搜索1：AI文档自动化最佳实践
   - 搜索2：document automation AI tools 2024
   - 搜索3：workflow automation with AI

3. **记忆沉淀** (self-improving)
   - 记录到 `projects/document-automation.md`
   - 提炼关键工具：nano-pdf, desktop-control, toryx-automation

4. **并行验证** (delegate-task)
   - 子任务1：测试 nano-pdf 编辑效率
   - 子任务2：测试 desktop-control 自动化可能性
   - 子任务3：调研各工具成本

5. **汇报结果**
   ```
   主人，根据我的调研和验证，推荐这个组合：
   
   📄 文档处理：nano-pdf（自然语言编辑PDF）
   🖥️ 桌面自动化：desktop-control（自动执行重复操作）
   🌐 浏览器操作：toryx-automation（网页数据抓取）
   
   已将这个方案记录到我的知识库，下次处理类似任务会自动使用。
   ```

---

## 自我进化机制

每次完成主动任务后，自动：

1. **记录到 memory.md**（如果高频使用）
2. **更新 SESSION-STATE.md**（当前任务状态）
3. **提炼到 corrections.md**（如果踩过坑）
4. **更新 owner-interests.json**（根据任务类型更新关键词）

---

## 禁止事项

- ❌ 不要在主人没要求时过度调研（浪费资源）
- ❌ 不要记录主人隐私信息到公开文件
- ❌ 不要在 self-improving 之外存储学习成果
- ❌ 不要忽略 WAL 触发条件（重要细节必须先记录）