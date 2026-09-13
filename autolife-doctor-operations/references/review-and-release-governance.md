# 评审与发布治理

用本流程处理 PR 评审、堆叠合并排序、发布就绪、制品溯源、分支保护，以及 v0.5 收尾追踪。

## 1. 建立新鲜的 GitHub 基线

在仓库根目录核实身份并查询当前状态：

```bash
git remote -v
git status --short --branch
git log --oneline --decorate -10
gh repo view --json nameWithOwner,defaultBranchRef,url
gh pr list --state open --limit 100 \
  --json number,title,headRefName,headRefOid,baseRefName,isDraft,mergeable,reviewDecision,statusCheckRollup,url
gh issue view 6 --json number,title,state,assignees,labels,body,url
```

不得沿用上一次运行得到的 PR 编号、head、检查、评审、可合并性或分支策略。分支保护要单独查询，404 应解读为"未受保护"，而不是 API 成功。

## 2. 按当前 head 评审每个 PR

按依赖顺序处理每个 PR：

1. 确认 base 分支与前置 PR 的关系。
2. 在当前 head SHA 上阅读 diff 与变更文件。
3. 检查是否混入无关生成数据、临时飞书草稿、密钥、凭据、私有证据、机器人载荷或二进制制品。
4. 当就绪、修复、证据、部署或授权语义发生变化时，核验安全不变量。
5. 按变更规模运行相称的测试。发布最终 stack 前，优先跑完仓库文档规定的完整质量套件。
6. 最后一次 push 之后重新查询检查。旧 SHA 上的绿色检查不能为当前 head 背书。
7. 查询已提交的评审与必需审批；评论或作者自评不构成独立审批。

常用查询：

```bash
gh pr view PR_NUMBER --json headRefOid,baseRefName,mergeable,reviewDecision,reviews,statusCheckRollup,files,commits
gh pr diff PR_NUMBER
gh pr checks PR_NUMBER
```

先报告发现。自动检查通过是证据，不是合并许可。

## 3. 保持 stack 的确定性

- 只按文档规定的依赖顺序合并或 rebase。
- 一次只合并一个 PR，然后重新查询下一个 PR 的 base、diff、head SHA、检查与评审。
- 平台自动重定向堆叠 PR 时，先核验重定向后的 diff 再继续。
- 不得 force-push、改写他人提交、绕过必需检查或直接推送 `main`。
- 保留一份映射：PR 编号、base SHA、head SHA、检查结论、评审决定、合并 commit。

## 4. 执行合并门禁

以下条件全部成立才可合并：

- 用户已授权合并动作；
- PR 非 draft 且在当前 head 可合并；
- 必需检查在同一 head 上全绿；
- 存在必需的独立人工审批；
- 涉及安全的变更有确定的安全或代码责任人，而不是编造的占位者；
- PR 描述涵盖证据、授权边界、部署、回滚和文档影响；
- 没有未解决的更高严重度评审发现。

若仓库未强制评审规则，不得把这一缺失当作批准。记录 `human_review_missing`，在授权范围内更新收尾追踪，然后在合并前停下。

## 5. 保护 `main`，但不编造治理

只有在用户授权仓库变更且真实评审角色已知后，才能启用或修改保护。目标策略应包含：

- 来自当前成功 workflow 的真实质量检查名称；
- 至少一个独立的批准评审；
- head 变化时对过期评审的 dismissal 或重新批准；
- 禁止 force push、禁止删除分支；
- 管理员行为要明确决定，而不是默认假设。

写入分支保护后重新读取响应确认。不得为了满足勾选项而创建虚构的 CODEOWNERS 团队。

## 6. 保全制品溯源

机器人金丝雀之前记录：

- 受保护发布分支上的源码合并 commit；
- workflow run 与成功的 job ID；
- 制品名称、SHA-256、Doctor 版本、目标架构、构建模式；
- 配置与修复策略的 SHA-256；
- 变更工单、维护窗口、回滚责任人、回滚制品 SHA-256。

绝不部署本地构建或 PR 分支的二进制，同时又将其描述为已评审的生产制品。

## 7. 更新收尾追踪

获得授权后，用事实更新当前发布 issue，而不是重写叙事：

- 当前 PR head 及审批/检查状态；
- 分支保护状态；
- 物理机器人可达性及时间戳；
- 新鲜的 `release-status` 与验证器结果；
- 金丝雀或回滚回执；
- 未解决的阻塞项、责任角色、下一步动作。

机器、治理、交付、文档四类门禁保持为独立的清单项。所有声明的退出条件都可独立验证后，才能关闭 issue。

## 退出状态

- `READY_FOR_REVIEW`：代码与测试就绪，等待独立审批。
- `READY_TO_MERGE`：当前 head 已评审、检查全绿、可合并且已明确授权。
- `MERGED_NOT_RELEASABLE`：源码已合并，但制品、所有权、机器人或金丝雀门禁未过。
- `RELEASABLE_FOR_CANARY`：制品溯源与全部金丝雀前门禁均为最新；这不等于生产成功。
- `HOLD`：指出第一个稳定的阻塞项，不得让 stack 静默前进。
