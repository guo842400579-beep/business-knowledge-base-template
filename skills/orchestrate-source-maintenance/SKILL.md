---
name: orchestrate-source-maintenance
description: 编排大型、多仓库或长期源码驱动的业务知识库维护，建立源码版本快照、入口清单、WIKI 覆盖矩阵、原子 finding、分批计划、恢复点、增量 stale 复核和绑定基线的独立终审。Use when 用户要求全量分析代码、跨系统维护 WIKI、评估源码覆盖率、恢复中断的大任务，或源码与知识库变化后的增量复核。
---

# 编排大型源码维护

负责全局盘点、范围控制、覆盖统计、批次、恢复和终审；把每个明确业务对象交给 `../extract-source-to-wiki/SKILL.md` 深度分析。

## 职责边界

- 清单、矩阵、进度、恢复点和终审回执只放 `.work/source-analysis/`。
- 不把机器扫描结果直接写入 WIKI 或 RAW。
- 源码仓库只读，不修改、格式化、生成或清理业务代码。
- 不以扫描文件数、Controller 数或生成文档数作为完成标准。
- `blocked-conflict` 不是完成状态。
- 历史终审绑定基线；基线变化后自动视为 `stale`。

## 前置阅读

依次读取：

1. `AGENTS.md`；
2. `WIKI/index.md`、概念 Index 和源码映射 Index；
3. `../extract-source-to-wiki/SKILL.md`；
4. [覆盖模型](references/coverage-model.md)；
5. 安排批次、恢复或终审时读取 [批次与终审手册](references/batch-playbook.md)。

## 初始化启动门

真实知识库进入大型源码维护前，`BOOTSTRAP_ONCE.md` 必须已删除或归档，业务边界和示例内容已替换，并且：

```bash
python3 skills/lint/scripts/lint_wiki.py --strict-init
```

返回 0。未通过时只做初始化或范围诊断，不建立正式覆盖基线。维护模板本身时不适用此门。

## 工作目录

同一维护项目持续复用同一个目录：

```text
.work/source-analysis/<YYYY-MM-DD>-<scope>/
├── repository-inventory.csv
├── source-entrypoints.csv
├── wiki-coverage.csv
├── cross-object-chains.csv
├── semantic-findings.csv
├── unmapped-entrypoints.csv
├── wiki-snapshot.json
├── batches.md
├── decisions.md
└── final-audit.md
```

- 不因对话中断或上下文压缩而重建批次根目录。
- 机器生成 CSV 默认拒绝覆盖，防止丢失人工分类。
- `decisions.md` 只记录范围取舍和冲突处理决定，不作为业务事实来源。
- `final-audit.md` 必须记录知识库 commit、工作区状态、工作区指纹和 `wiki_snapshot_sha256`。

## 工作流

### 1. 冻结范围

明确：

- 纳入的源码仓库、系统、业务域和跨对象链路；
- 外部系统、其他业务域、基础设施和历史逻辑等排除项；
- 每个仓库的路径、分支、完整 commit、工作区状态和必要指纹；
- 当前页面证据状态；
- 本轮完成口径和允许的排除状态。

源码工作区不干净时只读当前状态，不覆盖或清理改动。库存脚本记录 tracked diff 与 untracked 内容的指纹；指纹不能替代可重建 commit，终审时必须在同一工作树复核，或把对象标为 `needs-reproducible-source`。后端代码不能证明页面字段、按钮和 UI 形态。

### 2. 生成导航清单

运行通用库存脚本：

```bash
python3 skills/orchestrate-source-maintenance/scripts/build_source_inventory.py \
  --repo "示例系统A=/path/to/repository-a" \
  --repo "示例系统B=/path/to/repository-b" \
  --wiki-root WIKI \
  --output-dir .work/source-analysis/<YYYY-MM-DD>-<scope>
```

可选：

```bash
--profile generic
--profile spring-java
--coverage-root 功能模块
--coverage-root 概念
--coverage-root 操作流程
--mapping-root 源码映射
--include-ext .java --include-ext .kt
```

默认覆盖根为功能模块、概念和操作流程。页面映射直接落到 `WIKI/源码映射/<系统>/...`；概念和流程分别落到 `WIKI/源码映射/概念/`、`WIKI/源码映射/操作流程/`。

脚本只提供候选导航和 WIKI 内容快照，不产生业务结论，也不定义完整源码分母。它默认跳过常见测试、fixture、example 和构建目录；文件名和内容启发式仍会漏掉自定义框架、函数式入口、动态装配、SQL、消息配置或其他技术栈。必须再检查仓库结构、构建清单、路由/Resolver、proto/schema、消息与任务配置、存储过程和运行装配，并把漏项人工加入 `source-entrypoints.csv`。`spring-java` 只增强常见路由识别。

### 3. 校准覆盖矩阵

逐行判断 `wiki-coverage.csv`：

- 区分真实业务页、复杂功能、概念、流程、结构 Index 和明确排除项；
- 补充业务域、仓库、候选入口、优先级和页面证据；
- 机器无法可靠匹配的入口留在 `unmapped-entrypoints.csv`；
- 先匹配已有 WIKI 对象，再处理代码中发现但 WIKI 尚无对应对象的能力；
- 高价值入口最终必须有归属或明确分类，不能残留 `unassigned`。

同时校准 `cross-object-chains.csv`，补充每条流程涉及的业务对象、源码入口、版本和状态。机器生成的候选不是覆盖率分母；分母必须经人工冻结并记录纳入/排除理由。

受控值见[覆盖模型](references/coverage-model.md)。`source-entrypoints.csv` 是入口主表，`unmapped-entrypoints.csv` 只是待归属视图；人工分类只改主表，再重新生成或手工同步视图，不能让两份文件分叉成两个事实源。

### 4. 建立原子 Finding

`semantic-findings.csv` 至少记录：

```text
finding_id,coverage_row_id,business_conclusion,target_wiki_path,target_heading,
fusion_action,old_wording_action,source_mapping_path,blocker,review_notes,status
```

融合动作只使用：

- `rewrite-existing`
- `merge-table`
- `new-business-section`
- `link-only`
- `blocked`

禁止 `append-source-section`。技术证据留在源码映射，业务结论必须回到原字段、按钮、状态、流程、权限或下游章节。

### 5. 制定批次

优先级：

1. 金额、权限、状态机、删除和跨系统一致性；
2. 交易主链、审批和跨对象流程；
3. 配置保存校验与下游消费；
4. 导入导出、消息、任务、补偿和批处理；
5. 低风险查询和排除项复核。

批次规模：

- 跨系统、状态流转或复杂配置：1 个对象；
- 中等链路：最多 2 个对象；
- 简单只读查询：最多 3–4 个对象。

存在依赖时先分析基础概念或上游配置。不要在一批同时展开无关业务域。

### 6. 逐对象执行

为 `extract-source-to-wiki` 提供：

- 覆盖行 ID、目标 WIKI 和候选入口；
- 固定仓库、分支、commit 和工作区状态；
- 本批边界和依赖；
- 页面证据、已知冲突和原子 finding；
- 允许的扩大范围条件。

单对象只有同时完成以下内容才标记 `published`：

1. 源码映射；
2. 业务结论就近回写；
3. 相关 Index；
4. 两条以内 log；
5. 默认 lint；
6. 覆盖矩阵和 finding 回执。

### 7. 批次发布门

每批结束：

1. 核对仓库版本和调用链。
2. 核对业务结论去向和融合动作。
3. 核对页面能力分类、冲突和待确认项。
4. 运行默认 lint、相关页面纯化检查和 `git diff --check`。
5. 更新覆盖矩阵、finding、未归属入口和下批恢复点。
6. Audit 提示单独记录，不把它当发布失败。

### 8. 中断恢复

恢复时先读：

- 当前仓库和知识库状态；
- `batches.md` 最后恢复点；
- 覆盖矩阵、finding 和 decisions；
- 当前 WIKI 快照与旧终审基线。

以下情况重新打开对象：

- 源码 commit 变化并影响调用链；
- WIKI、页面证据或业务口径实质变化；
- 上游配置或公共依赖被修正；
- 原状态为 `needs-source`、`needs-page-evidence`、`needs-runtime-evidence`、`needs-reproducible-source`、`blocked-conflict` 或 `stale`，且条件已变化。

### 9. 增量复核

1. 记录新旧源码 commit、工作区指纹和新旧 WIKI 快照。
2. 把新库存输出到新的 `refresh-<date>/`，不得对含人工分类的活动目录使用 `--force`。
3. 对比新旧入口、WIKI 对象和链路，人工合并到主矩阵。
4. 反查受影响入口、覆盖行、链路和 finding。
5. 只把受影响对象标为 `stale`。
6. 公共枚举、基础服务、消息或远程接口变化时扩大一层影响分析。

### 10. 独立最终审计

逐批门禁全部完成后，使用新的审阅回合重新取证；优先由未执行该批次的代理/人员复核，至少不能复用批次中的“已通过”结论。重新读取当前文件、重算 WIKI 快照和源码版本后检查：

- 所有纳入对象是否终态；
- 高价值入口是否均已归属或解释；
- finding 是否全部有融合动作和终态；
- 是否存在统一源码追加专区、技术路径泄漏或重复权威位置；
- 源码映射、业务回写、Index 和链接是否一致；
- 冲突是否已关闭或批准排除；
- 默认 lint、纯化和 diff 是否通过；
- 当前知识库 commit、工作区状态和 WIKI 快照是否与终审基线一致。

把结果写入 `final-audit.md`。后续 WIKI 快照变化时，终审状态改为 `stale`，不得继续作为当前完成证明。

## 完成定义

只有同时满足以下条件，才能报告所选范围完成：

- 所有纳入 WIKI 对象为 `published`、`verified-no-source` 或明确批准的排除状态；
- 所有高价值源码入口已链接业务对象或明确分类；
- `unmapped-entrypoints.csv` 无未解释的高价值入口；
- 所有 finding 已融合、链接或明确阻断；
- 所有源码映射绑定具体 commit；
- 所有冲突已解决，或批准从当前完成范围排除；
- 默认 lint 通过，Audit 遗留单独报告；
- 独立终审通过且基线未过期。

分别报告：

- WIKI 对象闭环率；
- 高价值源码入口归属率；
- 跨对象链路闭环率；
- Finding 融合率；
- 版本新鲜度。
