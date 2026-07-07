---
name: lint
description: 业务知识库健康检查。Use when 用户要求检查知识库、修复断链、检查 frontmatter、检查 index 或完成维护后的验证。
version: 1.0.0
license: MIT
metadata:
  tags: [knowledge-base, lint, wiki]
  related_skills: [query]
---

# 知识库 Lint 工作流

## 何时使用

- 完成新增、移动、重命名或删除文档后。
- 用户要求“检查知识库”“lint”“检查一致性”。
- 发现断链、索引遗漏、frontmatter 缺失、表格渲染异常时。

## 推荐命令

```bash
python3 skills/lint/scripts/lint_wiki.py
python3 skills/lint/scripts/lint_wiki.py --fix
python3 skills/lint/scripts/lint_wiki.py --strict-init
```

脚本默认从当前模板根目录推断 `WIKI/` 路径，也支持：

```bash
python3 skills/lint/scripts/lint_wiki.py --root /path/to/your/wiki/WIKI
python3 skills/lint/scripts/lint_wiki.py --root /path/to/your/knowledge-base
```

## 检查范围

| 检查项 | 说明 |
|--------|------|
| 目录 index | 根目录需要 `index.md`；子目录需要 `{目录名}_index.md` |
| index 链接 | `_index.md` 中的链接必须存在 |
| index 覆盖 | 同目录普通 `.md` 应被 `_index.md` 引用或提及 |
| frontmatter | 普通页检查 `title/type/source/date`；index 页可无 `source` |
| source 可追溯 | 普通页 frontmatter 中的 `RAW_SOURCES/...` 路径必须存在 |
| Markdown 断链 | 本地链接必须指向存在的文件或目录 |
| 表格格式 | 检查 `|||`、列数不一致等常见问题 |
| 分享清洁度 | 检查 `.DS_Store`、`.idea` 等本地杂文件 |
| 初始化占位 | 使用 `--strict-init` 提醒 `<待填写>`、`示例...` 等未替换内容 |
| 一次性清单 | 使用 `--strict-init` 提醒初建完成后删除或归档 `BOOTSTRAP_ONCE.md` |

## 修复优先级

| 优先级 | 问题类型 |
|--------|----------|
| P0 | 断链、缺少必要 index、文件不可读 |
| P1 | 内容逻辑错误或跨文档冲突 |
| P2 | frontmatter 缺失、表格格式、index 覆盖不足 |
| P3 | 命名建议、结构建议 |

## 注意事项

- `RAW_SOURCES/` 不参与 lint，保持原始状态。
- 含表格的 Markdown 优先整文件重写，避免局部编辑破坏列数。
- 删除文件前先复制到 `文档备份/`。
- lint 脚本只做结构检查，不判断业务结论是否正确。
