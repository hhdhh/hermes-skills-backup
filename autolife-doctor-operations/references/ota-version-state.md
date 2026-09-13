# 机器人在跑哪个 OTA 版本

回答「这台机器人现在跑的是什么」「升级落地了没有」「机队里哪几台还没升上去」时用本流程。

## 先分清三个不同的问题

它们看着像一个问题，答案来自完全不同的地方，混用会得出自信而错误的结论：

| 问题 | 权威来源 | 怎么问 |
|---|---|---|
| 发布了什么 | `AutolifeOTAReleases` 的 CUE，CI 编译成 `catalog.json` | 读控制台页面或那个仓库 |
| 这台机器人在跑什么 | 机器人本地的 Btrfs 拓扑与 durable journal | `doctor --check ota_slot`，或登机 `ota-agent status` |
| 升级链路健不健康 | 机器人本地的 slot 事务状态 | 同上，看 `phase` |

**「已发布 0.5.2」不蕴含「robot-2 在跑 0.5.2」。** 控制台上的舰队表是机器人自报的，
一台从没上报过的机器人不会出现在那里——那不代表它不存在，也不代表它有问题。

## 用 Doctor 问

```bash
doctor --check ota_slot --format json
```

`value` 形如 `slot a · 3f2b1c8d9e4a`。`detail` 里除了摘要，还会带上 `ota-agent` 自己给出
的说明——**不要把它压缩掉**，那些说明区分了几种看起来一样、含义相反的情况。

### status 的含义

| status | phase | 意思 |
|---|---|---|
| `healthy` | `Committed` | 升级已提交为 last-known-good。稳定态 |
| `warning` | 其它 phase | 升级停在半路：候选已装未 bless、等重启、或已回滚。**不必然是故障**，但需要有人接手 |
| `critical` | `ManualIntervention` | 事务已停在人工介入状态，登机处理 |
| `unknown` | 无 | 读不到已提交事务。**这台机器人可能从未升级过——那是正常的**，不要当故障报 |

`unknown` 最容易误判。先看 `detail` 里的说明再下结论：「从未 staged 过升级」和「journal
损坏」都会让字段为空，但一个是正常状态，另一个是需要立即处理的完整性问题。

## 发货前的版本核对

期望版本的**编辑面**是飞书的发货核对表（两张：通用机器人、太空舱机器人），人在那里维护。
**可信源头**是它的快照 `data/version-checklist.json`——提交进 git，带着飞书 revision 与
内容摘要。机器人和 CI 只认快照，不读在线表。

这样分工不是多此一举。在线表缺四样发布链路需要的东西：改动**没有 review 门**（有编辑权
就立刻生效）、**不可内容寻址**（无法把「表的某一版」钉进一次发布让机器人自证）、**CI 读
不到**（要 Feishu 凭据，构建机不该持有）、**取表与用表之间会变**。快照把这四样补回来，
同时不夺走表的好处：人照旧在表里改。

```bash
# 1. 取表 → 快照（需要 lark-cli 已登录）。人 review 后提交。
tools/fetch_version_checklist.py --out data/version-checklist.json

# 2. 从快照生成探针配置
tools/checklist_to_probes.py --product general --out /etc/autolife/version-probes.toml

# 3. 机器人上核对——一屏列全所有组件
doctor --config /etc/autolife/doctor.toml versions
```

`doctor versions` 是发货核对要看的那一屏：每个组件一行，匹配的显示版本，不符的直接指出
实际值与期望值，读不到的说明是哪个字段缺失。最后一行是 OTA 运行版本。

它只做人看的视图。机器要读的形状用 `--once --format json`——那是带门禁判定与证据字段的
完整快照。不为 `versions` 再造一个 JSON 形状：同一份数据两种表达，下游要各自适配两遍。

TUI（直接跑 `doctor`）里这些也在，选中「环境库版本」或「OTA 运行版本」那行看详情即可。

产品线：`general`（通用机器人，17 个组件）、`capsule`（太空舱，6 个）。

生成的配置里钉着产品线、sheet id、飞书 revision 与快照摘要——**拿到一份配置能回答「它
来自表的哪一版」**。一份配置和一张表摆在一起却答不出这个问题，就没法判断它们是不是同
一件事，而那正是发货核对要回答的。

改版本的正确顺序：改表 → 重新取快照 → review 后提交 → 重新生成配置。**只改配置不改表**，
会让机器人按配置检查、人按表签字，两边各自为政。

### 取快照时要留意的

- **跳过的行**会打到 stderr（VR 软件、平板软件不在机器人上）。表里新加一行而脚本没认
  出来，配置就少一个组件，而所有检查照样绿——所以每次都看一眼那几行。
- **快照是确定性的**：同一份表重复取得到逐字节相同的文件。出现意外 diff 就是表真的改了。
  组件按名字排序而非行序，因为有人在表里插一行不该显示成大面积改动。
- **空结果是硬错误**，不会生成空快照。空快照会让 Doctor 报「未配置」，看起来像没启用
  检查而不是取表失败。
- `json_key` 由组件名把连字符换成下划线得到，沿用仓库既有配置，**是假设不是契约**。

> 长期看这些版本应该进 `AutolifeOTAReleases` 的 Release 清单，那时表退化为编辑面的一种。
> 在那之前，表 + 快照就是真源，不要在别处再维护第三份。

## Doctor 为什么不自己解析

`ota_slot` 只是调用 `ota-agent status` 并原样呈现它的答案。Doctor **不**自己去读 Btrfs
或解析 journal——那会成为第二个读取者，可以和 OTA 自己的读取结果不一致，而两边都会显得
像对的。这与当初删掉控制面那张目录投影是同一条理由。

改动 `ota_slot` 时守住这条：需要更多字段，就去 `ota-agent status` 加，不要在 Doctor 这边
另起一套解析。

## 权限边界

`ota-agent status` **不需要 root，也不挂载任何东西**——它只读 `/proc/self/mountinfo` 和
`@state` 里的 journal。这是它能被 Doctor 每分钟调用的前提。

需要完整拓扑（默认 slot、FSID、恢复决策）时才用 `ota-agent slot status`，它需要 root-only
的管理挂载。**Doctor 不应该调那个** ——健康检查器不该有挂载文件系统的能力。

## 边界：观察，不驱动

Doctor 回答「在跑什么」。它**不**发起升级。

升级只由设备侧发起（人在机器人上执行 `ota-agent`，或 VR 商店触发）。如果将来要让 Doctor
参与升级，先分清是哪一种：

- **Doctor 在机器人上决定去升级** —— 仍是拉模型，可以做。
- **Doctor 的服务端把升级推给机器人** —— 这是推模型从另一个门回来。审批、定向、
  Assignment 生命周期会跟着回来，而它们换不来安全收益：能升级机器人的人本来就在机器人
  跟前且持有 root。

要走第二条，先开 ADR 说明为什么设备侧发起不够用。

## 配置

```toml
[ota]
status_command = ["/usr/bin/ota-agent", "status"]
expected_closure = ""
```

`status_command` 留空即关闭这项检查——没装 OTA 的机器人不该因此报异常。

`expected_closure` 留空表示**只清点、不判断符合性**。「在跑什么」永远能回答；「是不是该
跑的那个」需要有人先写下期望值。填了之后，运行的 closure 与它不符会报 `warning`。

不要把期望值写死在这里当作机队标准——它是**这一台**机器人的期望。机队级的「谁该跑什么」
属于发布编排，在 `AutolifeOTAReleases`。
