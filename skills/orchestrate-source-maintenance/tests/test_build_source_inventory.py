#!/usr/bin/env python3
"""Regression tests for the source-maintenance inventory builder."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_source_inventory.py"
)


class SourceInventoryTests(unittest.TestCase):
    def run_script(
        self,
        source: Path,
        wiki: Path,
        output: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo",
                f"测试系统={source}",
                "--wiki-root",
                str(wiki),
                "--output-dir",
                str(output),
                *extra,
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def fixture(self, root: Path) -> tuple[Path, Path, Path]:
        source = root / "source"
        wiki = root / "knowledge" / "WIKI"
        output = root / "output"
        source.mkdir()
        (wiki / "功能模块" / "测试系统").mkdir(parents=True)
        (wiki / "概念").mkdir(parents=True)
        (wiki / "操作流程").mkdir(parents=True)
        (wiki / "功能模块" / "测试系统" / "页面.md").write_text(
            "---\ntitle: 测试页面\ntype: module\n---\n",
            encoding="utf-8",
        )
        (wiki / "概念" / "对象.md").write_text(
            "---\ntitle: 测试对象\ntype: concept\n---\n",
            encoding="utf-8",
        )
        (wiki / "操作流程" / "处理流程.md").write_text(
            "---\ntitle: 测试处理流程\ntype: process\n---\n",
            encoding="utf-8",
        )
        return source, wiki, output

    def test_empty_candidate_inventory_keeps_schema_and_marks_non_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, wiki, output = self.fixture(Path(temporary))
            (source / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
            result = self.run_script(source, wiki, output)
            self.assertEqual(result.returncode, 0, result.stdout)

            with (output / "source-entrypoints.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                reader = csv.DictReader(handle)
                self.assertIn("entry_id", reader.fieldnames or [])
                self.assertEqual(list(reader), [])

            with (output / "repository-inventory.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                repository = next(csv.DictReader(handle))
            self.assertEqual(repository["worktree"], "not-git")
            self.assertEqual(repository["commit"], "")
            self.assertEqual(repository["worktree_fingerprint"], "")

            snapshot = json.loads(
                (output / "wiki-snapshot.json").read_text(encoding="utf-8")
            )
            self.assertEqual(snapshot["knowledge_base_vcs"], "none")
            self.assertEqual(snapshot["knowledge_base_worktree"], "not-git")
            self.assertIn("knowledge_base_worktree_fingerprint", snapshot)

            with (output / "wiki-coverage.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                coverage = list(csv.DictReader(handle))
            page = next(row for row in coverage if row["coverage_kind"] == "功能模块")
            concept = next(row for row in coverage if row["coverage_kind"] == "概念")
            self.assertEqual(
                page["source_mapping_path"],
                "WIKI/源码映射/测试系统/页面.md",
            )
            self.assertEqual(page["mapping_exists"], "no")
            self.assertEqual(
                concept["source_mapping_path"],
                "WIKI/源码映射/概念/对象.md",
            )
            self.assertEqual(concept["mapping_exists"], "no")

            with (output / "cross-object-chains.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                chain = next(csv.DictReader(handle))
            self.assertEqual(chain["title"], "测试处理流程")

    def test_candidate_is_classified_and_overwrite_requires_force(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, wiki, output = self.fixture(Path(temporary))
            (source / "OrderController.py").write_text(
                '@app.get("/orders")\ndef list_orders():\n    return []\n',
                encoding="utf-8",
            )
            (source / "user.resolver.ts").write_text(
                "@Resolver()\nexport class UserResolver {}\n",
                encoding="utf-8",
            )
            (source / "mod.rs").write_text(
                'Router::new().route("/health", get(health))\n',
                encoding="utf-8",
            )
            first = self.run_script(source, wiki, output)
            self.assertEqual(first.returncode, 0, first.stdout)

            with (output / "source-entrypoints.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                entries = list(csv.DictReader(handle))
            by_path = {entry["relative_path"]: entry for entry in entries}
            self.assertEqual(
                by_path["OrderController.py"]["category"], "controller-api-router"
            )
            self.assertEqual(by_path["OrderController.py"]["routes"], "/orders")
            self.assertEqual(
                by_path["user.resolver.ts"]["category"], "graphql-resolver"
            )
            self.assertEqual(
                by_path["mod.rs"]["category"], "controller-api-router"
            )

            second = self.run_script(source, wiki, output)
            self.assertEqual(second.returncode, 1, second.stdout)
            self.assertIn("Refusing to overwrite", second.stdout)

            forced = self.run_script(source, wiki, output, "--force")
            self.assertEqual(forced.returncode, 0, forced.stdout)

    def test_unborn_staged_content_changes_fingerprint(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, wiki, output = self.fixture(Path(temporary))
            subprocess.run(
                ["git", "init", "-q", str(source)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            staged = source / "OrderService.py"
            staged.write_text("VALUE = 1\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(source), "add", "OrderService.py"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            first = self.run_script(source, wiki, output)
            self.assertEqual(first.returncode, 0, first.stdout)
            with (output / "repository-inventory.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                first_row = next(csv.DictReader(handle))

            staged.write_text("VALUE = 2\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(source), "add", "OrderService.py"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            second_output = Path(temporary) / "output-2"
            second = self.run_script(source, wiki, second_output)
            self.assertEqual(second.returncode, 0, second.stdout)
            with (second_output / "repository-inventory.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                second_row = next(csv.DictReader(handle))

            self.assertEqual(first_row["commit"], "")
            self.assertEqual(first_row["worktree"], "dirty")
            self.assertTrue(first_row["worktree_fingerprint"])
            self.assertNotEqual(
                first_row["worktree_fingerprint"],
                second_row["worktree_fingerprint"],
            )

            untracked = source / "未跟踪.txt"
            untracked.write_text("版本一\n", encoding="utf-8")
            third_output = Path(temporary) / "output-3"
            third = self.run_script(source, wiki, third_output)
            self.assertEqual(third.returncode, 0, third.stdout)
            with (third_output / "repository-inventory.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                third_row = next(csv.DictReader(handle))

            untracked.write_text("版本二\n", encoding="utf-8")
            fourth_output = Path(temporary) / "output-4"
            fourth = self.run_script(source, wiki, fourth_output)
            self.assertEqual(fourth.returncode, 0, fourth.stdout)
            with (fourth_output / "repository-inventory.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                fourth_row = next(csv.DictReader(handle))

            self.assertNotEqual(
                third_row["worktree_fingerprint"],
                fourth_row["worktree_fingerprint"],
            )

    def test_custom_feature_root_maps_directly_and_overlaps_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, wiki, output = self.fixture(root)
            custom = wiki / "自定义功能"
            custom.mkdir()
            (custom / "自定义功能_index.md").write_text(
                "---\ntitle: 自定义功能\ntype: index\n---\n",
                encoding="utf-8",
            )
            (custom / "页面.md").write_text(
                "---\ntitle: 自定义页面\ntype: module\n---\n",
                encoding="utf-8",
            )
            direct = self.run_script(
                source,
                wiki,
                output,
                "--feature-root",
                "自定义功能",
            )
            self.assertEqual(direct.returncode, 0, direct.stdout)
            with (output / "wiki-coverage.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            page = next(row for row in rows if row["title"] == "自定义页面")
            self.assertEqual(
                page["source_mapping_path"],
                "WIKI/源码映射/页面.md",
            )

            overlap = self.run_script(
                source,
                wiki,
                root / "overlap",
                "--coverage-root",
                "功能模块",
                "--coverage-root",
                "功能模块/测试系统",
            )
            self.assertEqual(overlap.returncode, 1, overlap.stdout)
            self.assertIn("must not overlap", overlap.stdout)

    def test_nested_standard_roots_preserve_namespace_and_chains(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, wiki, output = self.fixture(root)
            process_domain = wiki / "操作流程" / "子域"
            process_domain.mkdir()
            (process_domain / "子流程.md").write_text(
                "---\ntitle: 子流程\ntype: process\n---\n",
                encoding="utf-8",
            )
            result = self.run_script(
                source,
                wiki,
                output,
                "--coverage-root",
                "功能模块/测试系统",
                "--coverage-root",
                "操作流程/子域",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            with (output / "wiki-coverage.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            page = next(row for row in rows if row["title"] == "测试页面")
            self.assertEqual(page["coverage_kind"], "功能模块")
            self.assertEqual(page["system"], "测试系统")
            self.assertEqual(
                page["source_mapping_path"],
                "WIKI/源码映射/测试系统/页面.md",
            )
            with (output / "cross-object-chains.csv").open(
                encoding="utf-8-sig", newline=""
            ) as handle:
                chains = list(csv.DictReader(handle))
            self.assertEqual([row["title"] for row in chains], ["子流程"])


if __name__ == "__main__":
    unittest.main()
