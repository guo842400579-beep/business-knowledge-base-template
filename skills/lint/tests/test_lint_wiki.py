#!/usr/bin/env python3
"""Regression tests for the reusable knowledge-base lint script."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lint_wiki.py"


class LintFixture:
    def __init__(self, root: Path):
        self.root = root
        self.wiki = root / "WIKI"
        self.raw = root / "RAW_SOURCES"
        (self.wiki / "概念").mkdir(parents=True)
        (self.raw / "专家知识").mkdir(parents=True)
        (self.raw / "专家知识" / "证据.md").write_text("虚构证据\n", encoding="utf-8")
        (self.wiki / "index.md").write_text(
            """---
title: 测试知识库
type: index
date: 2026-07-23
updated: 2026-07-23
---

# 测试知识库

- [概念](./概念/概念_index.md)
""",
            encoding="utf-8",
        )
        (self.wiki / "概念" / "概念_index.md").write_text(
            """---
title: 概念索引
type: index
date: 2026-07-23
updated: 2026-07-23
---

# 概念索引

- [示例(新)](./示例(新).md)
""",
            encoding="utf-8",
        )
        (self.wiki / "概念" / "示例(新).md").write_text(
            """---
title: 示例
type: concept
source: |
  RAW_SOURCES/专家知识/证据.md
date: 2026-07-23
updated: 2026-07-23
---

# 示例

这是足够长的虚构业务正文，用于验证普通页面、来源和包含括号的本地链接。

```markdown
[代码围栏中的空链接]()
||| 代码围栏中的伪表格
```
""",
            encoding="utf-8",
        )

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )


class LintWikiTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return LintFixture(Path(temporary.name))

    def test_valid_fixture_and_code_fences_pass(self):
        fixture = self.fixture()
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("PASS", result.stdout)

    def test_source_must_be_a_file_under_raw(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8").replace(
                "RAW_SOURCES/专家知识/证据.md",
                "RAW_SOURCES/专家知识",
            ),
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("source 必须指向具体文件", result.stdout)

    def test_index_must_link_sibling_page(self):
        fixture = self.fixture()
        extra = fixture.wiki / "概念" / "未链接.md"
        extra.write_text(
            (fixture.wiki / "概念" / "示例(新).md")
            .read_text(encoding="utf-8")
            .replace("title: 示例", "title: 未链接"),
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("索引未以链接覆盖", result.stdout)

    def test_links_cannot_escape_knowledge_base(self):
        fixture = self.fixture()
        external = fixture.root.parent / f"external-{fixture.root.name}.md"
        external.write_text("outside\n", encoding="utf-8")
        self.addCleanup(external.unlink)
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8")
            + f"\n[库外文件](../../../{external.name})\n",
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("链接越出知识库根目录", result.stdout)

    def test_commonmark_angle_link_and_escaped_pipe_table_pass(self):
        fixture = self.fixture()
        spaced = fixture.wiki / "概念" / "名称 含空格.md"
        spaced.write_text(
            (fixture.wiki / "概念" / "示例(新).md")
            .read_text(encoding="utf-8")
            .replace("title: 示例", "title: 空格文件"),
            encoding="utf-8",
        )
        index = fixture.wiki / "概念" / "概念_index.md"
        index.write_text(
            index.read_text(encoding="utf-8")
            + "\n- [空格文件](<./名称 含空格.md>)\n"
            + "\n| 表达式 | 含义 |\n|--------|------|\n| A \\| B | 或关系 |\n",
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_nested_and_escaped_parenthesis_links_pass(self):
        fixture = self.fixture()
        nested = fixture.wiki / "概念" / "名称(第二版(新)).md"
        escaped = fixture.wiki / "概念" / "规则(旧).md"
        source = (fixture.wiki / "概念" / "示例(新).md").read_text(encoding="utf-8")
        nested.write_text(
            source.replace("title: 示例", "title: 嵌套括号"), encoding="utf-8"
        )
        escaped.write_text(
            source.replace("title: 示例", "title: 转义括号"), encoding="utf-8"
        )
        index = fixture.wiki / "概念" / "概念_index.md"
        index.write_text(
            index.read_text(encoding="utf-8")
            + "\n- [嵌套](./名称(第二版(新)).md)\n"
            + r"- [转义](./规则\(旧\).md)" + "\n",
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_reference_style_index_link_passes(self):
        fixture = self.fixture()
        index = fixture.wiki / "概念" / "概念_index.md"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "[示例(新)](./示例(新).md)",
                "[示例页面][example]\n\n[example]: <./示例(新).md>",
            ),
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_undefined_reference_style_link_fails(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8") + "\n[缺失引用][missing]\n",
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("引用式链接未定义", result.stdout)

    def test_invalid_short_table_separator_fails(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8") + "\n| A | B |\n|-|-|\n|x|y|\n",
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("至少需要三根横线", result.stdout)

    def test_audit_is_non_blocking(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8") + "\n尚未实采的虚构边界。\n",
            encoding="utf-8",
        )
        result = fixture.run("--audit")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("待完成内容", result.stdout)

    def test_share_and_initialization_checks_are_opt_in(self):
        fixture = self.fixture()
        (fixture.root / ".DS_Store").write_bytes(b"fixture")
        (fixture.root / "AGENTS.md").write_text("<待填写：业务域>\n", encoding="utf-8")

        default = fixture.run()
        self.assertEqual(default.returncode, 0, default.stdout)

        share = fixture.run("--share-check")
        self.assertEqual(share.returncode, 1, share.stdout)
        self.assertIn(".DS_Store", share.stdout)

        strict = fixture.run("--strict-init")
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("模板占位内容", strict.stdout)

    def test_strict_init_ignores_instructional_examples(self):
        fixture = self.fixture()
        (fixture.root / "README.md").write_text(
            "说明中的示例系统无需替换。\n", encoding="utf-8"
        )
        skill = fixture.root / "skills" / "example" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("用示例页面解释操作。\n", encoding="utf-8")
        answer = fixture.root / "知识库测试用例" / "答案" / "001.md"
        answer.parent.mkdir(parents=True)
        answer.write_text("DEMO-001 是虚构回归答案。\n", encoding="utf-8")

        strict = fixture.run("--strict-init")
        self.assertEqual(strict.returncode, 0, strict.stdout)

    def test_strict_init_follows_referenced_template_assets(self):
        fixture = self.fixture()
        sample = fixture.raw / "设计文档" / "示例字段模板.md"
        sample.parent.mkdir(parents=True)
        sample.write_text("DEMO-001\n", encoding="utf-8")
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8").replace(
                "RAW_SOURCES/专家知识/证据.md",
                "RAW_SOURCES/设计文档/示例字段模板.md",
            ),
            encoding="utf-8",
        )
        strict = fixture.run("--strict-init")
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("模板示例证据", strict.stdout)

    def test_strict_init_non_utf8_agents_is_controlled(self):
        fixture = self.fixture()
        (fixture.root / "AGENTS.md").write_bytes(b"\xffbroken")
        strict = fixture.run("--strict-init")
        self.assertEqual(strict.returncode, 1, strict.stdout)
        self.assertIn("文件读取失败", strict.stdout)
        self.assertNotIn("Traceback", strict.stdout)

    def test_safe_fix_does_not_change_legitimate_empty_cells(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        table = "\n||| A | B |\n|---|---|---|---|\n|x|y|z|w|\n"
        page.write_text(page.read_text(encoding="utf-8") + table, encoding="utf-8")
        before = page.read_text(encoding="utf-8")
        result = fixture.run("--fix")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(page.read_text(encoding="utf-8"), before)

    def test_safe_fix_repairs_only_confirmed_extra_pipes(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_text(
            page.read_text(encoding="utf-8")
            + "\n| A | B |\n|---|---|\n||| x | y |\n",
            encoding="utf-8",
        )
        result = fixture.run("--fix")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("| x | y |", page.read_text(encoding="utf-8"))
        self.assertNotIn("||| x | y |", page.read_text(encoding="utf-8"))

    def test_sensitive_scan_checks_names_text_types_and_encoding(self):
        fixture = self.fixture()
        (fixture.root / "SECRET-safe.md").write_text("clean\n", encoding="utf-8")
        (fixture.root / "safe.html").write_text("SECRET\n", encoding="utf-8")
        undecodable = fixture.root / "bad.txt"
        undecodable.write_bytes(b"\xffSECRET")

        result = fixture.run("--sensitive-term", "SECRET")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("文件或目录名命中", result.stdout)
        self.assertIn("safe.html", result.stdout)
        self.assertIn("敏感词扫描未完成", result.stdout)

    def test_encoding_errors_are_controlled(self):
        fixture = self.fixture()
        page = fixture.wiki / "概念" / "示例(新).md"
        page.write_bytes(b"\xffbroken")
        wiki_result = fixture.run("--audit")
        self.assertEqual(wiki_result.returncode, 1, wiki_result.stdout)
        self.assertIn("读取失败", wiki_result.stdout)
        self.assertNotIn("Traceback", wiki_result.stdout)

        terms = fixture.root / "terms.txt"
        terms.write_bytes(b"\xffSECRET")
        term_result = fixture.run("--sensitive-file", str(terms))
        self.assertEqual(term_result.returncode, 2, term_result.stdout)
        self.assertIn("Failed to read sensitive file", term_result.stdout)
        self.assertNotIn("Traceback", term_result.stdout)

    def test_non_utf8_root_index_is_controlled(self):
        fixture = self.fixture()
        (fixture.wiki / "index.md").write_bytes(b"\xffbroken")
        result = fixture.run("--audit")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("读取失败", result.stdout)
        self.assertNotIn("Traceback", result.stdout)

    def test_index_filename_cannot_bypass_source(self):
        fixture = self.fixture()
        fake = fixture.wiki / "概念" / "待确认项_index.md"
        fake.write_text(
            """---
title: 伪装决策
type: decision
date: 2026-07-23
updated: 2026-07-23
---

# 伪装决策
""",
            encoding="utf-8",
        )
        index = fixture.wiki / "概念" / "概念_index.md"
        index.write_text(
            index.read_text(encoding="utf-8")
            + "\n- [伪装决策](./待确认项_index.md)\n",
            encoding="utf-8",
        )
        result = fixture.run()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("index 文件名必须使用 type: index", result.stdout)
        self.assertIn("非 index 文档缺少非空 source", result.stdout)

    def test_sensitive_scan_includes_dotenv_and_bom_term_file(self):
        fixture = self.fixture()
        (fixture.root / ".env").write_text("TOKEN=SECRET\n", encoding="utf-8")
        (fixture.root / ".env.local").write_text(
            "TOKEN=SECRET\n", encoding="utf-8"
        )
        terms = fixture.root / "terms.txt"
        terms.write_text("SECRET\n", encoding="utf-8-sig")
        result = fixture.run("--sensitive-file", str(terms))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(".env", result.stdout)
        self.assertIn(".env.local", result.stdout)
        self.assertIn("命中用户提供的敏感词", result.stdout)


if __name__ == "__main__":
    unittest.main()
