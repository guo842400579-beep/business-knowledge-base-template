# 对外分享检查清单

> 本清单用于把真实知识库、模板副本或示例包交给外部人员前的最终检查。关键词扫描不能替代图片、二进制文件和 Git 历史复核。

## 1. 分享范围

- 明确本次分享的根目录和目标接收者。
- 不从正在使用的真实知识库直接打包；优先复制到单独的分享目录后检查。
- 确认 `.work/`、真实 RAW、私有敏感词文件和本地凭据不在分享范围。

## 2. 文本和文件名

- 检查真实公司、系统、域名、组织、客户、人员、账号、手机号、邮箱、单号和金额。
- 检查文件名、目录名、frontmatter、链接文字、注释、CSV/JSON/YAML/Python 等文本文件。
- 检查 `文档备份/`，避免旧版本仍保留已删除的敏感内容。

```bash
python3 skills/lint/scripts/lint_wiki.py --share-check
python3 skills/lint/scripts/lint_wiki.py --sensitive-file /private/path/sensitive_terms.txt
```

## 3. 图片和二进制资产

- 人工查看截图中的姓名、头像、手机号、邮箱、账号、组织、客户、单号、金额和浏览器地址栏。
- 打开 PDF、Word、Excel、PowerPoint、压缩包和导入模板，检查正文、批注、隐藏工作表、文档属性和文件名。
- 不能只依赖 `rg`；它不会可靠检查图片和多数二进制格式。

## 4. 临时层和本地杂文件

- `.work/` 必须被 `.gitignore` 忽略。
- 清理分享副本中的 `.DS_Store`、`.idea`、`__pycache__`、`*.pyc`、临时下载和编辑器备份。
- 不分享浏览器存储、认证缓存、工具日志或调试快照。

## 5. Git 历史

- 检查当前待提交文件和未跟踪文件。
- 检查敏感内容是否曾进入历史；仅从当前文件删除并不能清除历史。
- 如历史中存在敏感内容，停止分享并使用经过审查的历史清理方案；必要时轮换已经暴露的凭据。

## 6. 最终验证

```bash
python3 skills/lint/scripts/lint_wiki.py
python3 skills/lint/scripts/lint_wiki.py --audit
git diff --check
git status --short
```

记录：

- 分享目录；
- 检查日期；
- 使用的敏感词来源；
- 图片和二进制资产是否人工复核；
- 已知保留边界；
- 审核人或批准人。
