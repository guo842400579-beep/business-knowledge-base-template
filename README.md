# 业务知识库模板

这是一套去业务化、可长期维护的业务知识库骨架。它保留了结构化 WIKI、不可变证据、页面实采、源码映射、长任务恢复、待确认项、发布检查和少量虚构示例，不包含任何真实业务规则、组织名称、系统地址、人员信息或源码版本。

## 快速开始

1. 复制本目录并改名。
2. 先读 `AGENTS.md`。
3. 按 `BOOTSTRAP_ONCE.md` 完成首次业务边界、系统、角色、菜单和索引初始化。
4. 删除虚构 WIKI、示例截图路径和模板日志，改为真实、已脱敏内容。
5. 初始化完成后删除该文件，或归档到 `文档备份/`，并让 `--strict-init` 通过。
6. 日常维护按对应 Skill 执行，并通过发布门。

```bash
python3 skills/lint/scripts/lint_wiki.py
git diff --check
```

## 四层结构

```text
.work/         临时进度、候选证据、恢复点和终审回执；不提交，不作为业务事实
    ↓ 筛选
RAW_SOURCES/   最小充分的永久证据；只增不删
    ↓ 提炼
WIKI/          默认查询的稳定知识
    ↓ 审计
WIKI/log.md    每次最多两条简短变更记录
```

页面实采时，不要把所有截图和 DOM 直接倒入 RAW；先在 `.work/page-capture/` 探索，再提升能独立支撑结论的最小集合。大型源码任务在 `.work/source-analysis/` 维护覆盖矩阵、批次和恢复点。

## 维护模式

| 模式 | 适用场景 | Skill |
|------|----------|-------|
| 页面实采 | 记录菜单、字段、按钮、Tab、宽表、弹窗和风险提示 | `record-feature-to-wiki` |
| 单对象源码分析 | 追踪一个页面、配置、概念或业务链路 | `extract-source-to-wiki` |
| 大型源码维护 | 全仓、多仓、覆盖率、长期恢复或增量复核 | `orchestrate-source-maintenance` |
| RAW 提取 | 从手册、QA、表格、专家知识和用户反馈提炼业务知识 | 按 `AGENTS.md` 执行 |
| 查询 | 从索引和业务正文回答，并说明来源与边界 | `query` |
| 验证 | 检查结构、证据、链接、索引、纯度和分享风险 | `lint` |

## 默认查询边界

日常业务问题默认只查 WIKI 的索引、概念、功能模块和操作流程正文，不读取：

- `.work/`
- `RAW_SOURCES/`
- `WIKI/log.md`
- `文档备份/`

只有用户要求证据或历史、正文有歧义、存在信息边界，或需要核对源码版本时，才定向读取对应证据。`WIKI/待确认项/` 只用于限定答案，不代表已确认事实。

## 发布检查

### 确定性门禁

```bash
python3 skills/lint/scripts/lint_wiki.py
```

检查 frontmatter、source、断链、空链接、index 覆盖、表格、行号污染和明确维护过程噪声。P0/P1/P2 会阻断发布。

### 非阻断审计

```bash
python3 skills/lint/scripts/lint_wiki.py --audit
```

汇总成熟度、可能的过程语言、正文偏短、索引更新时间滞后和状态冲突。Audit 需要人工判断，不阻断发布。

### 页面纯化

```bash
python3 skills/record-feature-to-wiki/scripts/check_wiki_purity.py WIKI/本次修改文件.md
```

WIKI 应只保留稳定事实和必要信息边界；按钮清单、截图归档、未点击保存、工具报错和完成凭证留在 `.work/`。

### 初始化和分享

```bash
python3 skills/lint/scripts/lint_wiki.py --strict-init
python3 skills/lint/scripts/lint_wiki.py --share-check
python3 skills/lint/scripts/lint_wiki.py \
  --sensitive-term "公司名" \
  --sensitive-term "系统域名"
```

- 原始模板运行 `--strict-init` 时出现虚构占位提示属于预期。
- `--strict-init` 只检查真实业务配置、WIKI、截图路径及 WIKI 仍引用的模板示例资产；Skill、说明文档和回归用例中的虚构示例可以保留。
- `--share-check` 用于发现 `.DS_Store`、`.idea` 等本地杂文件。
- 敏感词文件可通过 `--sensitive-file /private/path/terms.txt` 传入，不应提交到模板。

## 大型源码维护

`orchestrate-source-maintenance` 会在 `.work/source-analysis/<scope>/` 建立：

- 仓库版本清单；
- 源码入口清单；
- WIKI 覆盖矩阵；
- 跨对象链路矩阵；
- 未归属高价值入口；
- 批次、恢复点和范围决策；
- 绑定基线版本的独立终审。

不能用“读取了多少文件”或“生成了多少文档”代替完成度。应分别核算 WIKI 对象、源码入口和跨对象链路。基线之后有业务文档变化时，旧终审视为过期。

库存脚本只给候选导航。自定义框架、函数式路由、Resolver、消息、任务、proto/schema、存储过程和动态装配必须人工补齐；机器扫描数量不能直接作为覆盖率分母。

## 模板中的示例

模板只保留一个虚构概念、页面、流程、待确认项和源码映射入口，用来演示：

- frontmatter 和真实 `source` 文件引用；
- 概念、页面、流程和待确认项的关系；
- index 落位和文档颗粒度；
- 页面事实、业务规则和源码实现的边界。

示例不是业务建议。真实建库后应替换或删除。

## 对外分享

分享前阅读 `SHARING_CHECKLIST.md`。至少检查：

- 文本和文件名；
- 图片、PDF、Office 和压缩包内容；
- `文档备份/`；
- `.work/` 是否被 Git 忽略；
- Git 历史中是否曾提交敏感内容；
- 真实 RAW 是否被误带入模板。

关键词扫描只是其中一步，不能替代视觉和二进制资产复核。
