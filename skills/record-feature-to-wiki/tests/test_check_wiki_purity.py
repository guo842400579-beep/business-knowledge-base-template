#!/usr/bin/env python3
"""Regression tests for the WIKI purity checker."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_wiki_purity.py"
)


class WikiPurityTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def test_clean_and_review_only_content_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            page = Path(temporary) / "page.md"
            page.write_text("当前样本只验证了只读状态。\n", encoding="utf-8")
            result = self.run_script(str(page))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("REVIEW", result.stdout)
        self.assertIn("PASS", result.stdout)

    def test_hard_process_noise_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            page = Path(temporary) / "page.md"
            page.write_text("截图已归档。\n", encoding="utf-8")
            result = self.run_script(str(page))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("FAIL", result.stdout)

    def test_unknown_option_and_missing_path_fail(self):
        unknown = self.run_script("--wiki-root", "WIKI")
        self.assertEqual(unknown.returncode, 2, unknown.stdout)

        missing = self.run_script("/definitely/not/a/real/wiki/path")
        self.assertEqual(missing.returncode, 2, missing.stdout)
        self.assertIn("Path does not exist", missing.stdout)

    def test_non_utf8_markdown_is_controlled(self):
        with tempfile.TemporaryDirectory() as temporary:
            page = Path(temporary) / "page.md"
            page.write_bytes(b"\xffbroken")
            result = self.run_script(str(page))
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("Cannot read", result.stdout)
        self.assertNotIn("Traceback", result.stdout)


if __name__ == "__main__":
    unittest.main()
