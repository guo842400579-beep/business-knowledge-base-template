# 覆盖模型

## 目录

1. 覆盖对象
2. WIKI 对象状态
3. 源码入口分类
4. 原子 Finding
5. 矩阵字段
6. 覆盖率口径

## 1. 覆盖对象

### WIKI 对象

功能页面、概念、流程和有独立业务语义的复杂入口。结构 Index 进入候选后，再人工判定为 `not-applicable`。

每个纳入对象都有独立映射目标：页面直接镜像系统/菜单路径，概念和流程分别进入源码映射下的同名目录。若当前仓库确认无相关实现，可使用 `verified-no-source`；不能因对象不是页面而跳过证据闭环。

### 源码入口

Controller、API、Router、Facade、Application Service、Handler、Validator、Rule、Strategy、Repository、消息、任务和远程调用入口。

DTO、PO、枚举、工具类和框架层通常只作为业务链路证据，不自动成为独立覆盖对象。

### 跨对象链路

跨页面、跨角色、跨系统或跨仓库的交易、审批、履约、状态流转和补偿链路。单个页面发布不能替代整条链路覆盖。

## 2. WIKI 对象状态

| 状态 | 含义 | 完成 |
|------|------|------|
| `untriaged` | 尚未判断是否纳入 | 否 |
| `planned` | 已确认入口、边界和批次 | 否 |
| `analyzing` | 正在追踪 | 否 |
| `needs-source` | 缺少必要源码或入口 | 否 |
| `needs-page-evidence` | 代码存在，但页面能力或形态未实采 | 否 |
| `needs-runtime-evidence` | 静态代码不足以证明当前部署、配置或数据条件下生效 | 否 |
| `needs-reproducible-source` | 源码工作树无法冻结或复核 | 否 |
| `blocked-conflict` | 正式规则、页面、RAW 与源码冲突 | 否 |
| `published` | 映射、业务回写、Index、log、lint 和矩阵回执闭环 | 是 |
| `verified-no-source` | 已检索并记录当前仓库无对应实现的理由 | 是 |
| `out-of-scope-external` | 外部系统或跳转，批准排除 | 是 |
| `out-of-scope-other-domain` | 其他业务域，批准排除 | 是 |
| `not-applicable` | 纯结构 Index 等无需独立分析 | 是 |
| `stale` | 源码、WIKI 或业务证据变化，需要复核 | 否 |

`blocked-conflict` 只能在明确批准排除并记录理由后从当前完成范围扣除，不能直接计作完成。

## 3. 源码入口分类

- `linked-page`
- `linked-concept`
- `linked-process`
- `linked-config`
- `page-not-provided`
- `page-not-inspected`
- `other-business-branch`
- `legacy-or-dead`
- `infrastructure`
- `supporting-source`
- `unassigned`

完成时高价值入口不得保留 `unassigned`。

## 4. 原子 Finding

每条业务结论单独记录，避免一个 finding 同时改写多个不相干口径。

融合动作：

| 动作 | 含义 |
|------|------|
| `rewrite-existing` | 修正既有权威位置 |
| `merge-table` | 合并到既有字段、规则或状态表 |
| `new-business-section` | 新增确有独立语义的业务小节 |
| `link-only` | 正文已有结论，只补证据链接 |
| `blocked` | 冲突未裁决，暂停回写 |

禁止 `append-source-section`。

## 5. 矩阵字段

`wiki-coverage.csv`：

```text
row_id,coverage_kind,system,wiki_path,title,object_type,source_mapping_path,mapping_exists,
analysis_status,priority,source_repositories,candidate_entrypoints,page_evidence_status,
conclusion_status,assigned_batch,last_verified_commit,notes
```

`source-entrypoints.csv`：

```text
entry_id,system,repository,module,category,symbol,routes,relative_path,
classification,linked_wiki_rows,last_verified_commit,
last_verified_worktree_fingerprint,notes
```

`semantic-findings.csv`：

```text
finding_id,coverage_row_id,business_conclusion,target_wiki_path,target_heading,
fusion_action,old_wording_action,source_mapping_path,blocker,review_notes,status
```

`cross-object-chains.csv`：

```text
chain_id,wiki_path,title,participating_objects,source_entrypoints,status,
last_verified_commits,notes
```

受控值：

- `priority`: `critical` / `high` / `medium` / `low`
- `conclusion_status`: `not-reviewed` / `drafted` / `integrated` / `blocked`
- finding `status`: `open` / `integrated` / `blocked` / `excluded`
- chain `status`: 使用 WIKI 对象状态中的 `untriaged`、`planned`、`analyzing`、`published`、各类 `needs-*`、`blocked-conflict`、`stale` 或批准排除状态

## 6. 覆盖率口径

分别报告：

- WIKI 对象闭环率；
- 高价值源码入口归属率；
- 跨对象链路闭环率；
- Finding 融合率；
- 版本新鲜度。

计算口径：

```text
WIKI 对象闭环率 = published 或 verified-no-source 的纳入对象 / 纳入业务对象
入口归属率 = 非 unassigned 的纳入高价值入口 / 纳入高价值入口
链路闭环率 = published 的纳入链路 / 纳入跨对象链路
Finding 融合率 = integrated 的纳入 finding / 纳入 finding
版本新鲜度 = 基线未变化的已闭环对象 / 已闭环对象
```

结构 Index 和批准排除项不进入业务闭环率分母，但必须保留排除理由。机器候选数不能直接作为分母；分母在人工校准后冻结。
