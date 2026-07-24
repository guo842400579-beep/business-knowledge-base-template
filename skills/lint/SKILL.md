---
name: lint
description: 对业务知识库执行确定性发布门、非阻断内容审计、初始化占位检查、分享清洁度检查和用户指定敏感词扫描。Use when 用户要求检查知识库、lint、一致性、断链、frontmatter、source、index、表格、WIKI 纯度、初始化状态或分享风险，或完成维护后的验证。
---

# 知识库 Lint

先检查确定性结构和可追溯性，再把需要业务判断的成熟度问题作为非阻断审计单独报告。不要把 Audit 提示等同于发布失败。

## 前置阅读

检查前先读：

1. `AGENTS.md`；
2. `WIKI/index.md`；
3. `WIKI/概念/概念_index.md`；
4. 本次修改过的文件。

默认只读。只有用户要求修复，或当前任务本身包含维护，才修改文件。

## 确定性发布门

```bash
python3 skills/lint/scripts/lint_wiki.py
```

检查：

| 检查项 | 级别 | 说明 |
|--------|------|------|
| WIKI 根 index | P0 | 必须存在 `WIKI/index.md` |
| 子目录 index | P0 | 含直接 Markdown 的目录必须有同名 `_index.md` |
| Markdown 链接 | P0 | 检查空链接、断链和越出知识库根目录；支持尖括号空格路径 |
| Frontmatter 结构 | P0/P1 | 起止符，`title/type/date/updated` 非空，以及合法 `type` |
| Source 可追溯 | P0/P1 | 普通页必须引用 RAW 下存在的具体文件 |
| Index 覆盖 | P2 | 覆盖同目录页面和直接子目录入口 |
| 表格格式 | P2 | 列数、行首多余竖线；忽略代码围栏 |
| 行号污染 | P0 | 检查误粘贴的读取行号前缀 |
| 硬性过程噪声 | P1 | WIKI 不得含按钮清单、截图已归档等维护流水 |

退出码：

- `0`：确定性门禁通过；
- `1`：发现 P0/P1/P2；
- `2`：参数或知识库根目录无效。

`WIKI/log.md` 属于审计层，不参与业务正文的 frontmatter/source/纯度检查。

## 非阻断内容审计

```bash
python3 skills/lint/scripts/lint_wiki.py --audit
```

在默认门禁之外汇总：

- 待补充、尚未实采等成熟度标记；
- 本轮、未点击、当前样本等可能的过程语言；
- 正文偏短；
- Index `updated` 落后于子文档；
- 同一目标在多个 Index 中出现完成/未完成状态冲突；
- Index 中的临时进度图标或日期。

这些提示可能是合法信息边界，必须人工判断。默认 lint 为 `0`、Audit 有提示时，正确表述是：

> 结构门禁通过，仍有内容优化项。

## 安全修复

```bash
python3 skills/lint/scripts/lint_wiki.py --fix
```

`--fix` 只在原列数不匹配、且移除候选行首竖线后恰好与分隔行一致时修复，然后自动重跑全部检查。合法空单元格、转义竖线和代码 span 中的竖线不会被改动。它不自动处理：

- 表格列数不一致；
- source、链接或 Index 缺失；
- frontmatter 内容；
- 待完成、过程语言和业务冲突。

含表格的 Markdown 应读取当前文件后整文件重写，不做脆弱的局部表格 patch。

## 指定路径

`--root` 同时接受知识库根目录和 `WIKI/` 目录：

```bash
python3 skills/lint/scripts/lint_wiki.py --root /path/to/knowledge-base
python3 skills/lint/scripts/lint_wiki.py --root /path/to/knowledge-base/WIKI
```

有效知识库必须同时存在 `WIKI/` 和 `RAW_SOURCES/`。

## 初始化检查

```bash
python3 skills/lint/scripts/lint_wiki.py --strict-init
```

检查会成为真实业务内容的 `AGENTS.md`、`WIKI/`、截图证据路径、WIKI 实际引用的模板示例资产，以及 `BOOTSTRAP_ONCE.md` 是否仍有 `<待填写>`、示例系统、示例概念、示例页面、示例流程或虚构编号等模板残留。

`README.md`、Skill 说明、分享清单和查询回归用例会长期保留虚构示例，因此不纳入该检查。

原始模板运行时出现这些提示属于预期；从模板创建真实知识库并完成初始化后，必须处理到通过。

## 分享清洁度

```bash
python3 skills/lint/scripts/lint_wiki.py --share-check
```

检查 `.DS_Store`、`.idea`、`.vscode`、缓存、交换/备份文件和被带入分享包的 `.work` 等本地杂项。分享检查不放入日常结构门禁，避免用户本地编辑器状态阻断业务文档发布。

分享前还要人工复核图片、PDF、Office、压缩包、备份和 Git 历史。

## 敏感词

```bash
python3 skills/lint/scripts/lint_wiki.py \
  --sensitive-term "公司名" \
  --sensitive-term "系统域名"

python3 skills/lint/scripts/lint_wiki.py \
  --sensitive-file /private/path/sensitive_terms.txt
```

敏感词文件每行一个，空行和 `#` 注释会跳过。扫描覆盖文件/目录名和常见文本类型，并尝试 UTF-8 与 GB18030；声明为文本但无法解码时阻断，避免假通过。私有敏感词文件不得提交到模板。

## 页面纯化

对本次页面实采或 RAW 回写的 WIKI 文件运行：

```bash
python3 skills/record-feature-to-wiki/scripts/check_wiki_purity.py WIKI/文件.md
```

- 硬性过程噪声返回失败；
- 可能合法的信息边界只提示人工判断；
- 不传文件或找不到 Markdown 时返回参数错误。

## 修复顺序

1. 运行默认 lint。
2. 修 P0：根目录、断链、source、frontmatter 结构、行号污染。
3. 修 P1：元数据、目录型 source、硬性过程噪声、敏感词。
4. 修 P2：表格和 Index 覆盖。
5. 重跑默认 lint。
6. 运行 `--audit`，单独报告非阻断项。
7. 对页面维护文件运行纯化检查。
8. 运行 `git diff --check`。

不要为了通过 lint：

- 删除或改写 RAW；
- 伪造 source；
- 弱化业务事实；
- 把冲突静默合并；
- 把页面内按钮伪装成菜单；
- 删除合法的信息边界。

## 日志

只读检查且未改文件，不写日志。

实际修复后追加：

```markdown
## [YYYY-MM-DD] lint | 知识库健康检查
- 修复：...
- 验证：默认 lint 通过；Audit 遗留 ... 项。
```

每次最多两条 bullet。

## 验证清单

- [ ] 默认 lint 退出码为 0。
- [ ] 普通页 source 指向 RAW 下具体文件。
- [ ] 本地链接和 Index 入口有效。
- [ ] 无表格列数、行号污染和硬性过程噪声。
- [ ] `--audit` 已单独查看，没有被误报为发布失败。
- [ ] 页面维护文件通过纯化检查。
- [ ] 真实建库后运行了 `--strict-init`。
- [ ] 分享前运行了 `--share-check` 和用户指定敏感词扫描。
- [ ] `git diff --check` 通过。
