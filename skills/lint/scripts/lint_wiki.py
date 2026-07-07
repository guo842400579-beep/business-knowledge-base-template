#!/usr/bin/env python3
"""
Generic business knowledge base lint script.
Checks WIKI markdown files for index structure, links, frontmatter and tables.

Usage:
  python3 skills/lint/scripts/lint_wiki.py
  python3 skills/lint/scripts/lint_wiki.py --fix
  python3 skills/lint/scripts/lint_wiki.py --strict-init
  python3 skills/lint/scripts/lint_wiki.py --root /path/to/WIKI
  python3 skills/lint/scripts/lint_wiki.py --root /path/to/knowledge-base
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional


class Issue(NamedTuple):
    severity: str
    file: str
    line: Optional[int]
    msg: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=None, help='Path to knowledge-base root or WIKI directory')
    parser.add_argument('--fix', action='store_true', help='Fix simple table pipe issues')
    parser.add_argument('--strict-init', action='store_true', help='Warn about template placeholders left in a real knowledge base')
    parser.add_argument('--sensitive-term', action='append', default=[], help='Sensitive term to scan for; may be repeated')
    parser.add_argument('--sensitive-file', type=Path, default=None, help='File containing sensitive terms, one per line')
    return parser.parse_args()


def normalize_wiki_root(path: Path) -> Path:
    path = path.resolve()
    if path.name == 'WIKI':
        return path
    if (path / 'WIKI').is_dir():
        return path / 'WIKI'
    return path


def knowledge_base_root(wiki_root: Path) -> Path:
    if wiki_root.name == 'WIKI':
        return wiki_root.parent
    return wiki_root


def default_wiki_root() -> Path:
    start = Path(__file__).resolve().parent
    for candidate in [start, *start.parents]:
        if candidate.name == 'WIKI':
            return candidate
        wiki_dir = candidate / 'WIKI'
        if wiki_dir.is_dir():
            return wiki_dir
    return start.parents[2] / 'WIKI'


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def iter_markdown_links(content: str):
    yield from re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', content)


def is_external_link(link: str) -> bool:
    return link.startswith(('http://', 'https://', 'mailto:', '#')) or '://' in link


def resolve_link(base: Path, wiki_root: Path, link: str) -> Path:
    clean = link.split('#', 1)[0].strip()
    if clean.startswith('/'):
        return wiki_root / clean.lstrip('/')
    return (base / clean).resolve()


def check_index_structure(wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    if not (wiki_root / 'index.md').exists():
        issues.append(Issue('P0', '.', None, 'WIKI 根目录缺少 index.md'))

    for directory in sorted(p for p in wiki_root.rglob('*') if p.is_dir()):
        md_files = list(directory.glob('*.md'))
        if not md_files:
            continue
        expected = directory / f'{directory.name}_index.md'
        if directory == wiki_root:
            continue
        if not expected.exists():
            issues.append(Issue('P0', rel(directory, wiki_root), None, f'目录缺少 index 文件，应为: {expected.name}'))

    for idx_file in sorted(wiki_root.rglob('*_index.md')) + ([wiki_root / 'index.md'] if (wiki_root / 'index.md').exists() else []):
        try:
            content = idx_file.read_text(encoding='utf-8')
        except OSError as exc:
            issues.append(Issue('P0', rel(idx_file, wiki_root), None, f'读取失败: {exc}'))
            continue
        for match in iter_markdown_links(content):
            link = match.group(2).strip()
            if is_external_link(link):
                continue
            target = resolve_link(idx_file.parent, wiki_root, link)
            if link.split('#', 1)[0].strip() and not target.exists():
                issues.append(Issue('P0', rel(idx_file, wiki_root), None, f'index 链接不存在: {link}'))
    return issues


def check_index_completeness(wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    for idx_file in sorted(wiki_root.rglob('*_index.md')):
        try:
            content = idx_file.read_text(encoding='utf-8')
        except OSError:
            continue
        linked_names = set()
        for match in iter_markdown_links(content):
            link = match.group(2).strip()
            if is_external_link(link):
                continue
            linked_names.add(Path(link.split('#', 1)[0]).name)
        text_without_links = re.sub(r'\[([^\]]+)\]\([^)]+\)', '', content)
        for md_file in sorted(idx_file.parent.glob('*.md')):
            if md_file.name == idx_file.name:
                continue
            if md_file.name in linked_names or md_file.stem in text_without_links:
                continue
            issues.append(Issue('P2', rel(idx_file, wiki_root), None, f"同目录文件未在 index 中引用或提及: {md_file.name}"))
    return issues


def column_count(line: str) -> int:
    if not line.strip().startswith('|'):
        return 0
    cells = line.strip().split('|')
    if cells and cells[0] == '':
        cells = cells[1:]
    if cells and cells[-1] == '':
        cells = cells[:-1]
    return len(cells)


def check_tables(content: str, filepath: Path, wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    lines = content.splitlines()
    for number, line in enumerate(lines, 1):
        if re.match(r'\|\|\|', line) or re.match(r'\|\| \|', line):
            issues.append(Issue('P2', rel(filepath, wiki_root), number, f'表格行首疑似多竖线: {line[:80]}'))

    i = 0
    while i < len(lines) - 1:
        header = lines[i].strip()
        sep = lines[i + 1].strip()
        if header.startswith('|') and sep.startswith('|') and re.fullmatch(r'[|:\- ]+', sep):
            expected = column_count(sep)
            header_cols = column_count(header)
            if expected != header_cols:
                issues.append(Issue('P2', rel(filepath, wiki_root), i + 1, f'表头列数({header_cols})与分隔行列数({expected})不一致'))
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                row = lines[i].strip()
                if not re.fullmatch(r'[|:\- ]+', row):
                    cols = column_count(row)
                    if cols != expected:
                        issues.append(Issue('P2', rel(filepath, wiki_root), i + 1, f'数据行列数({cols})与表头列数({expected})不一致'))
                i += 1
            continue
        i += 1
    return issues


def check_line_number_pollution(content: str, filepath: Path, wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    for number, line in enumerate(content.splitlines(), 1):
        if re.match(r'^\s*[0-9]{2,6}\|', line):
            issues.append(Issue('P0', rel(filepath, wiki_root), number, '疑似误粘贴读取行号前缀'))
    return issues


def check_frontmatter(content: str, filepath: Path, wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    lines = content.splitlines()
    if not lines:
        issues.append(Issue('P2', rel(filepath, wiki_root), None, '空文件'))
        return issues
    if lines[0].strip() != '---':
        issues.append(Issue('P2', rel(filepath, wiki_root), None, '缺少 frontmatter'))
        return issues
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == '---')
    except StopIteration:
        issues.append(Issue('P2', rel(filepath, wiki_root), None, 'frontmatter 未闭合'))
        return issues
    fm = '\n'.join(lines[1:end])
    is_index = (
        filepath.name == 'index.md'
        or filepath.name.endswith('_index.md')
        or re.search(r'^type:\s*index\s*$', fm, re.MULTILINE)
    )
    required = ['title:', 'type:', 'date:'] + ([] if is_index else ['source:'])
    for field in required:
        if field not in fm:
            issues.append(Issue('P2', rel(filepath, wiki_root), None, f'frontmatter 缺少字段: {field}'))
    issues.extend(check_frontmatter_sources(fm, filepath, wiki_root))
    return issues


def check_frontmatter_sources(fm: str, filepath: Path, wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    kb_root = knowledge_base_root(wiki_root)
    lines = fm.splitlines()
    in_source_block = False

    for index, line in enumerate(lines, 2):
        stripped = line.strip()
        if line.startswith('source:'):
            value = line.split(':', 1)[1].strip()
            in_source_block = value in {'', '|', '>'}
            if value and value not in {'|', '>'}:
                issues.extend(check_source_path(value, filepath, wiki_root, kb_root, index))
            continue

        if in_source_block:
            if not stripped:
                continue
            if line.startswith((' ', '\t')):
                issues.extend(check_source_path(stripped, filepath, wiki_root, kb_root, index))
                continue
            in_source_block = False

    return issues


def check_source_path(raw_value: str, filepath: Path, wiki_root: Path, kb_root: Path, line: int) -> List[Issue]:
    value = raw_value.strip().strip('`').strip('"').strip("'")
    if not value.startswith('RAW_SOURCES/'):
        return []
    if (kb_root / value).exists():
        return []
    return [Issue('P0', rel(filepath, wiki_root), line, f'frontmatter source 引用不存在: {value}')]


def check_links(content: str, filepath: Path, wiki_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    for match in iter_markdown_links(content):
        link = match.group(2).strip()
        if is_external_link(link):
            continue
        clean = link.split('#', 1)[0].strip()
        if not clean:
            continue
        target = resolve_link(filepath.parent, wiki_root, clean)
        if not target.exists():
            line = content[:match.start()].count('\n') + 1
            issues.append(Issue('P0', rel(filepath, wiki_root), line, f'断链: {link}'))
    return issues


def check_share_artifacts(kb_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    artifact_names = {'.DS_Store', '.idea'}
    for path in sorted(kb_root.rglob('*')):
        if path.name not in artifact_names:
            continue
        issues.append(Issue('P2', rel(path, kb_root), None, '分享前应清理本地编辑器或系统杂文件'))
    return issues


def check_initialization_placeholders(kb_root: Path) -> List[Issue]:
    issues: List[Issue] = []
    bootstrap_file = kb_root / 'BOOTSTRAP_ONCE.md'
    if bootstrap_file.exists():
        issues.append(Issue('P3', rel(bootstrap_file, kb_root), None, '首次建库完成后应删除或归档一次性清单'))
    patterns = ['<待填写：', '示例系统A', '示例系统B', '角色甲', '角色乙']
    for filepath in sorted(kb_root.rglob('*.md')):
        if '.git' in filepath.parts:
            continue
        try:
            content = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            issues.append(Issue('P0', rel(filepath, kb_root), None, f'文件读取失败: {exc}'))
            continue
        for number, line in enumerate(content.splitlines(), 1):
            if any(pattern in line for pattern in patterns):
                issues.append(Issue('P3', rel(filepath, kb_root), number, '真实建库前应替换模板占位内容'))
                break
    return issues


def load_sensitive_terms(args: argparse.Namespace) -> List[str]:
    terms = [term.strip() for term in args.sensitive_term if term.strip()]
    if args.sensitive_file:
        try:
            for line in args.sensitive_file.read_text(encoding='utf-8').splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    terms.append(stripped)
        except OSError as exc:
            raise RuntimeError(f'Failed to read sensitive file: {args.sensitive_file}: {exc}') from exc
    seen = set()
    unique_terms = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        unique_terms.append(term)
    return unique_terms


def iter_share_text_files(kb_root: Path):
    suffixes = {'.md', '.txt', '.yaml', '.yml', '.json', '.csv', '.py'}
    for filepath in sorted(kb_root.rglob('*')):
        if not filepath.is_file():
            continue
        if '.git' in filepath.parts:
            continue
        if filepath.suffix.lower() not in suffixes:
            continue
        yield filepath


def check_sensitive_terms(kb_root: Path, terms: List[str]) -> List[Issue]:
    issues: List[Issue] = []
    if not terms:
        return issues
    for filepath in iter_share_text_files(kb_root):
        try:
            content = filepath.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            issues.append(Issue('P0', rel(filepath, kb_root), None, f'文件读取失败: {exc}'))
            continue
        for number, line in enumerate(content.splitlines(), 1):
            for term in terms:
                if term in line:
                    issues.append(Issue('P1', rel(filepath, kb_root), number, f'命中用户提供的敏感词: {term}'))
    return issues


def fix_content(content: str) -> str:
    fixed = []
    for line in content.splitlines():
        if re.match(r'\|\|\|', line):
            line = line[1:]
        elif re.match(r'\|\| \|', line):
            line = '|' + line[3:]
        fixed.append(line)
    return '\n'.join(fixed) + ('\n' if content.endswith('\n') else '')


def main() -> int:
    args = parse_args()
    wiki_root = normalize_wiki_root(args.root) if args.root else default_wiki_root().resolve()
    kb_root = knowledge_base_root(wiki_root)
    if not wiki_root.exists():
        print(f'WIKI directory not found: {wiki_root}', file=sys.stderr)
        return 2

    issues: List[Issue] = []
    try:
        sensitive_terms = load_sensitive_terms(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    md_files = sorted(wiki_root.rglob('*.md'))
    issues.extend(check_index_structure(wiki_root))
    issues.extend(check_index_completeness(wiki_root))
    issues.extend(check_share_artifacts(kb_root))
    if args.strict_init:
        issues.extend(check_initialization_placeholders(kb_root))
    issues.extend(check_sensitive_terms(kb_root, sensitive_terms))

    for filepath in md_files:
        try:
            content = filepath.read_text(encoding='utf-8')
        except OSError as exc:
            issues.append(Issue('P0', rel(filepath, wiki_root), None, f'文件读取失败: {exc}'))
            continue
        issues.extend(check_frontmatter(content, filepath, wiki_root))
        issues.extend(check_tables(content, filepath, wiki_root))
        issues.extend(check_links(content, filepath, wiki_root))
        issues.extend(check_line_number_pollution(content, filepath, wiki_root))

    if args.fix:
        fixed_count = 0
        for filepath in md_files:
            content = filepath.read_text(encoding='utf-8')
            fixed = fix_content(content)
            if fixed != content:
                filepath.write_text(fixed, encoding='utf-8')
                fixed_count += 1
        if fixed_count:
            print(f'Fixed simple table pipe issues in {fixed_count} files. Please rerun lint.')
            return 1

    print(f'Scanned: {wiki_root}')
    print(f'Markdown files: {len(md_files)}')
    if not issues:
        print('PASS: no issues found.')
        return 0

    print(f'FAIL: {len(issues)} issues found.\n')
    grouped: Dict[str, List[Issue]] = {}
    for issue in sorted(issues, key=lambda item: (item.severity, item.file, item.line or 0)):
        grouped.setdefault(issue.severity, []).append(issue)
    for severity in ['P0', 'P1', 'P2', 'P3']:
        if severity not in grouped:
            continue
        print(f'{severity} ({len(grouped[severity])})')
        for issue in grouped[severity]:
            loc = f':{issue.line}' if issue.line else ''
            print(f'  {issue.file}{loc} - {issue.msg}')
        print()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
