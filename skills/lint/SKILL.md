---
name: lint
description: 业务知识库健康检查。Use when 用户要求检查知识库、lint、检查一致性、修复断链、检查 frontmatter、检查 index、检查表格、检查敏感信息，或完成维护后的验证。
version: 1.1.0
license: MIT
metadata:
  tags: [knowledge-base, lint, wiki, consistency-check]
  related_skills: [query, record-feature-to-wiki, extract-source-to-wiki]
---

# 知识库 Lint 工作流

## 核心原则

Lint 先检查结构和可追溯性，再处理内容一致性。脚本负责发现通用结构问题，人工负责判断业务结论是否正确。

不要把业务专有规则硬编码进模板 lint。模板只能保留通用规则：index、frontmatter、source、断链、表格、行号污染、初始化占位、分享清洁度和用户指定敏感词。

## 何时使用

- 完成新增、移动、重命名或删除文档后。
- 完成页面实采、RAW 提取或源码映射回写后。
- 用户要求“检查知识库”“lint”“检查一致性”“修复知识库问题”。
- 发现断链、索引遗漏、frontmatter 缺失、表格渲染异常、来源缺失或疑似敏感信息时。
- 对外分享模板或从模板创建真实知识库前。

## 前置预热

检查前先读：

| 文件 | 目的 |
|------|------|
| `AGENTS.md` | 确认目录规范、frontmatter 要求、RAW 只增不删和日志要求 |
| `WIKI/index.md` | 确认全库结构和当前模块入口 |
| `WIKI/概念/概念_index.md` | 建立概念背景，避免机械修复破坏业务含义 |

如果本次 lint 是某次维护后的验证，还要读本次修改过的文件。

## 推荐命令

```bash
# 只读检查
python3 skills/lint/scripts/lint_wiki.py

# 修复简单表格行首多竖线问题；修完后必须重跑只读检查
python3 skills/lint/scripts/lint_wiki.py --fix

# 真实建库或分享前检查模板占位
python3 skills/lint/scripts/lint_wiki.py --strict-init

# 指定知识库根目录或 WIKI 目录
python3 skills/lint/scripts/lint_wiki.py --root /path/to/knowledge-base
python3 skills/lint/scripts/lint_wiki.py --root /path/to/knowledge-base/WIKI
```

敏感词检查：

```bash
# 单个或多个敏感词
python3 skills/lint/scripts/lint_wiki.py --sensitive-term "公司名" --sensitive-term "系统域名"

# 从文件读取敏感词，每行一个；空行和 # 注释会跳过
python3 skills/lint/scripts/lint_wiki.py --sensitive-file sensitive_terms.txt
```

敏感词文件不应提交到可分享模板；建议放在本地临时目录或私有路径。

## 自动检查范围

| 检查项 | 严重级别 | 说明 |
|--------|----------|------|
| WIKI 根 `index.md` | P0 | 根目录必须存在 `WIKI/index.md` |
| 子目录 `_index.md` | P0 | 含 `.md` 的子目录必须有 `{目录名}_index.md` |
| index 链接有效性 | P0 | `_index.md` 和 `index.md` 中本地链接必须存在 |
| Markdown 断链 | P0 | 正文本地链接必须指向存在文件或目录 |
| frontmatter | P2 | 普通页检查 `title/type/source/date`；index 页可无 `source` |
| source 可追溯 | P0 | `RAW_SOURCES/...` 路径必须存在 |
| index 覆盖 | P2 | 同目录普通 `.md` 应被 `_index.md` 链接或提及 |
| 表格格式 | P2 | 检查 `|||`、`|| |`、列数不一致 |
| 行号污染 | P0 | 检查误粘贴的 `220|`、`   220|` 等读取行号 |
| 分享清洁度 | P2 | 检查 `.DS_Store`、`.idea` 等本地杂文件 |
| 初始化占位 | P3 | `--strict-init` 检查 `<待填写>`、示例系统和一次性清单 |
| 敏感词 | P1 | 用户通过参数提供的敏感词命中 |

`RAW_SOURCES/` 是原始证据，不参与结构 lint；但 frontmatter 中引用的 RAW 路径必须存在。

## 检查顺序

1. 运行只读 lint。
2. 先修 P0：断链、缺失 index、source 不存在、文件不可读、行号污染。
3. 再修 P1：敏感词、业务内容冲突或高风险错误。
4. 再修 P2：frontmatter、表格、index 覆盖、分享杂文件。
5. 最后处理 P3：命名建议、初始化占位、一次性文件。
6. 每次修复后重跑 lint，直到通过或明确说明剩余问题为什么暂不处理。

## 修复规则

- 编辑前必须读取当前文件。
- 含表格 Markdown 优先整文件重写或脚本生成，不要随手局部改 `|`。
- 删除或大改文件前先复制到 `文档备份/`。
- 重命名或移动文件后，搜索旧路径并同步更新：
  - frontmatter `related`
  - 正文 Markdown 链接
  - 各级 `_index.md`
  - `WIKI/index.md`
  - `WIKI/log.md`
- `--fix` 只适合修复简单行首多竖线；表格列数不一致必须人工读文件后修。
- 不要为了通过 lint 删除 RAW、伪造 source、移除用户反馈或弱化业务事实。

## 备用命令

脚本不可用时，用以下命令辅助：

```bash
# 文件结构
find WIKI -type f -name "*.md" | sort

# 表格行首异常
rg -n "\|\|\||\|\| \|" WIKI

# 本地链接和旧路径
rg -n "旧文件名|旧路径" WIKI

# 行号污染
rg -n "^\s*[0-9]{2,6}\|" WIKI

# 分享前检查本地杂文件
find . -name ".DS_Store" -o -name ".idea"
```

敏感信息检查应由用户提供真实关键词，模板中不要硬编码真实公司名、域名、人员名、手机号、邮箱、合同号或订单号。

## 业务一致性人工检查

脚本不能判断业务结论是否正确。做较大维护后，人工检查：

- 页面实采事实是否优先于源码推断。
- 源码映射是否只放证据链，业务结论是否回写到功能模块、概念或流程。
- 示例数据是否被标为示例，没有被写成枚举全集。
- 用户反馈是否先保留原文，再经确认写成业务结论。
- 页面未观察到或代码-only 能力是否没有被写成普通页面功能。
- 新增页面、Tab、按钮或流程是否有 RAW 证据和 index/log 闭环。

## `WIKI/log.md` 要求

如果 lint 触发了实际修复，应追加日志：

```markdown
## [YYYY-MM-DD] lint | 知识库健康检查
- 修复：...
- 验证：`python3 skills/lint/scripts/lint_wiki.py` 通过
- 遗留：...
```

如果只是只读检查且未修改文件，可以不写日志；但最终回复需说明检查结果。

## Verification Checklist

- [ ] `WIKI/index.md` 存在且链接有效。
- [ ] 所有含 `.md` 的子目录都有 `_index.md`。
- [ ] 同目录普通 `.md` 已被对应 `_index.md` 链接或提及。
- [ ] 普通页 frontmatter 包含 `title/type/source/date`。
- [ ] frontmatter `source` 指向真实 `RAW_SOURCES/...`。
- [ ] 无 Markdown 断链。
- [ ] 无 `|||`、`|| |` 或表格列数不一致。
- [ ] 无行号前缀污染。
- [ ] 重命名或移动后所有引用已同步。
- [ ] `--strict-init` 已用于真实建库或分享前检查。
- [ ] 如用户提供敏感词，已运行敏感词扫描。
- [ ] 本次修复已更新相关 index 和 `WIKI/log.md`。
