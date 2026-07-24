#!/usr/bin/env python3
"""Check WIKI Markdown for maintenance-process noise."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


HARD_NOISE = (
    "截图已归档",
    "浏览器已恢复",
    "释放控制",
    "运行全库 lint",
    "同步更新全局索引",
    "完成凭证",
    "按钮清单",
)

REVIEW_PHRASES = (
    "本轮",
    "本次采集",
    "本次实采",
    "本次操作",
    "本次未",
    "实采时",
    "未点击",
    "点击取消",
    "当前样本",
    "待复核",
    "待补采",
)


def markdown_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() == ".md":
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.md"))
    return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check WIKI Markdown for maintenance-process noise."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="One or more WIKI Markdown files or directories.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    files: list[Path] = []
    for path in args.paths:
        if not path.exists():
            print(f"Path does not exist: {path}", file=sys.stderr)
            return 2
        matched = markdown_files(path)
        if not matched:
            print(f"No Markdown files found at: {path}", file=sys.stderr)
            return 2
        files.extend(matched)

    files = sorted({path.resolve() for path in files if path.name != "log.md"})
    if not files:
        print("No WIKI Markdown files remain after excluding log.md.", file=sys.stderr)
        return 2

    hard_hits: list[str] = []
    review_hits: list[str] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"Cannot read {path}: {exc}", file=sys.stderr)
            return 2
        for line_no, line in enumerate(content.splitlines(), 1):
            for phrase in HARD_NOISE:
                if phrase in line:
                    hard_hits.append(f"{path}:{line_no}: {phrase}: {line.strip()}")
            for phrase in REVIEW_PHRASES:
                if phrase in line:
                    review_hits.append(f"{path}:{line_no}: {phrase}: {line.strip()}")

    if review_hits:
        print("REVIEW: possible process language or legitimate evidence boundaries")
        for hit in review_hits:
            print(f"  {hit}")

    if hard_hits:
        print("\nFAIL: maintenance-process noise found")
        for hit in hard_hits:
            print(f"  {hit}")
        return 1

    print("\nPASS: no hard maintenance-process noise found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
