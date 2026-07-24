#!/usr/bin/env python3
"""Lint a reusable business knowledge base.

Default mode is a deterministic publication gate. ``--audit`` adds non-blocking
content-quality findings. Initialization, sharing, and sensitive-term checks are
opt-in so local editor state does not block routine WIKI publication.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, NamedTuple, Optional
from urllib.parse import unquote


ALLOWED_TYPES = {"concept", "module", "process", "source-map", "decision", "index"}
REQUIRED_FIELDS = {"title", "type", "date", "updated"}
HARD_PROCESS_NOISE = (
    "截图已归档",
    "浏览器已恢复",
    "释放控制",
    "运行全库 lint",
    "同步更新全局索引",
    "完成凭证",
    "按钮清单",
)
AUDIT_MARKERS = {
    "待完成内容": ("🚧", "待记录", "待补充", "尚未实采", "待后续", "需后续"),
    "采集过程语言": (
        "本轮",
        "本次采集",
        "本次实采",
        "实采时",
        "未点击",
        "当前样本",
        "待复核",
        "待补采",
    ),
}
INDEX_PROGRESS_MARKERS = ("✅", "🚧", "⬜", "🆕", "记录中", "实采日期", "完成日期")
INITIALIZATION_MARKERS = (
    "<待填写",
    "示例系统A",
    "示例系统B",
    "示例系统",
    "角色甲",
    "角色乙",
    "示例概念",
    "示例页面",
    "示例流程",
    "DEMO-001",
)
INITIALIZATION_SAMPLE_ASSETS = {
    "RAW_SOURCES/设计文档/示例字段模板.md",
    "RAW_SOURCES/专家知识/示例专家补充.md",
}
SHARE_ARTIFACT_NAMES = {
    ".DS_Store",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "Thumbs.db",
    "__pycache__",
}
SHARE_TEXT_SUFFIXES = {
    ".bash",
    ".cfg",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".gql",
    ".gradle",
    ".graphql",
    ".htm",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".kt",
    ".less",
    ".log",
    ".md",
    ".php",
    ".properties",
    ".proto",
    ".py",
    ".rb",
    ".rs",
    ".scss",
    ".sh",
    ".sql",
    ".svelte",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}
SHARE_TEXT_NAMES = {
    ".editorconfig",
    ".env",
    ".gitattributes",
    ".gitignore",
    ".npmrc",
    "Dockerfile",
    "Makefile",
}


class Issue(NamedTuple):
    severity: str
    file: str
    line: Optional[int]
    msg: str


class MarkdownLink(NamedTuple):
    label: str
    destination: str
    offset: int
    unresolved_reference: bool = False


@dataclass
class Frontmatter:
    fields: dict[str, str]
    field_lines: dict[str, int]
    source_entries: list[tuple[str, int]]
    end_line: int


KB_ROOT: Path
WIKI_ROOT: Path
RAW_ROOT: Path


def discover_kb_root() -> Optional[Path]:
    start = Path(__file__).resolve().parent
    for candidate in (start, *start.parents):
        if (candidate / "WIKI").is_dir() and (candidate / "RAW_SOURCES").is_dir():
            return candidate
    return None


def normalize_kb_root(path: Path) -> Optional[Path]:
    resolved = path.expanduser().resolve()
    if resolved.name == "WIKI":
        candidate = resolved.parent
    else:
        candidate = resolved
    if (candidate / "WIKI").is_dir() and (candidate / "RAW_SOURCES").is_dir():
        return candidate
    return None


def relative_wiki(path: Path) -> str:
    try:
        return str(path.relative_to(WIKI_ROOT))
    except ValueError:
        return str(path)


def relative_kb(path: Path) -> str:
    try:
        return str(path.relative_to(KB_ROOT))
    except ValueError:
        return str(path)


def line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def fenced_lines(content: str) -> set[int]:
    result: set[int] = set()
    fence: Optional[str] = None
    for number, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        marker = "```" if stripped.startswith("```") else "~~~" if stripped.startswith("~~~") else None
        if marker:
            result.add(number)
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
        elif fence:
            result.add(number)
    return result


def scalar_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1].strip()
    return stripped


def parse_frontmatter(content: str, filepath: Path) -> tuple[Optional[Frontmatter], list[Issue]]:
    issues: list[Issue] = []
    lines = content.splitlines()
    rel = relative_wiki(filepath)
    if not lines or lines[0].strip() != "---":
        return None, [Issue("P0", rel, 1, "缺少 frontmatter 起始分隔符 '---'")]

    end_index = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end_index is None:
        return None, [Issue("P0", rel, 1, "frontmatter 未闭合，缺少结束分隔符 '---'")]

    fields: dict[str, str] = {}
    field_lines: dict[str, int] = {}
    source_entries: list[tuple[str, int]] = []
    current_field: Optional[str] = None
    field_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")

    for index in range(1, end_index):
        raw_line = lines[index]
        match = field_re.match(raw_line)
        if match:
            current_field = match.group(1)
            value = match.group(2).strip()
            fields[current_field] = value
            field_lines[current_field] = index + 1
            if current_field == "source" and value not in {"", "|", ">", "|-", ">-"}:
                source_entries.append((scalar_value(value).strip("`"), index + 1))
            continue

        if current_field == "source" and raw_line.strip():
            if not raw_line.startswith((" ", "\t")):
                current_field = None
                continue
            value = raw_line.strip()
            if value.startswith("- "):
                value = value[2:].strip()
            source_entries.append((scalar_value(value).strip("`"), index + 1))

    frontmatter = Frontmatter(fields, field_lines, source_entries, end_index + 1)
    for field in sorted(REQUIRED_FIELDS):
        if not scalar_value(fields.get(field, "")):
            issues.append(
                Issue(
                    "P1",
                    rel,
                    field_lines.get(field),
                    f"frontmatter 缺少或留空字段: {field}",
                )
            )

    doc_type = scalar_value(fields.get("type", ""))
    if doc_type and doc_type not in ALLOWED_TYPES:
        issues.append(
            Issue(
                "P1",
                rel,
                field_lines.get("type"),
                f"frontmatter type 非法: '{doc_type}'，允许值为 {sorted(ALLOWED_TYPES)}",
            )
        )

    filename_is_index = filepath.name == "index.md" or filepath.name.endswith(
        "_index.md"
    )
    if filename_is_index and doc_type and doc_type != "index":
        issues.append(
            Issue(
                "P1",
                rel,
                field_lines.get("type"),
                "index 文件名必须使用 type: index",
            )
        )
    if doc_type == "index" and not filename_is_index:
        issues.append(
            Issue(
                "P1",
                rel,
                field_lines.get("type"),
                "type: index 仅用于 index.md 或 *_index.md",
            )
        )
    if doc_type != "index" and not source_entries:
        issues.append(
            Issue(
                "P1",
                rel,
                field_lines.get("source"),
                "非 index 文档缺少非空 source 条目",
            )
        )
    return frontmatter, issues


def check_sources(frontmatter: Optional[Frontmatter], filepath: Path) -> list[Issue]:
    if frontmatter is None:
        return []
    issues: list[Issue] = []
    rel = relative_wiki(filepath)
    raw_root = RAW_ROOT.resolve()
    for source, number in frontmatter.source_entries:
        source_path = source.split("#", 1)[0].strip()
        if not source_path:
            issues.append(Issue("P0", rel, number, "source 路径为空"))
            continue
        candidate = Path(source_path)
        if candidate.is_absolute() or not source_path.startswith("RAW_SOURCES/"):
            issues.append(
                Issue(
                    "P0",
                    rel,
                    number,
                    f"source 必须是 RAW_SOURCES 下的相对路径: '{source}'",
                )
            )
            continue
        resolved = (KB_ROOT / candidate).resolve()
        try:
            resolved.relative_to(raw_root)
        except ValueError:
            issues.append(Issue("P0", rel, number, f"source 越出 RAW_SOURCES: '{source}'"))
            continue
        if not resolved.exists():
            issues.append(Issue("P0", rel, number, f"source 文件不存在: '{source}'"))
        elif not resolved.is_file():
            issues.append(
                Issue(
                    "P1",
                    rel,
                    number,
                    f"source 必须指向具体文件，不能指向目录: '{source}'",
                )
            )
    return issues


def markdown_links(content: str) -> Iterable[tuple[MarkdownLink, int]]:
    fenced = fenced_lines(content)
    definitions: dict[str, str] = {}
    definition_pattern = re.compile(
        r"""(?m)^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*(?:<([^>\n]+)>|(\S+))"""
    )
    for match in definition_pattern.finditer(content):
        number = line_number(content, match.start())
        if number in fenced:
            continue
        key = " ".join(match.group(1).split()).casefold()
        definitions[key] = match.group(2) or match.group(3)

    found: list[MarkdownLink] = []
    cursor = 0
    length = len(content)
    while cursor < length:
        opening = content.find("[", cursor)
        if opening == -1:
            break
        closing = opening + 1
        while closing < length:
            if content[closing] == "\\":
                closing += 2
                continue
            if content[closing] == "]":
                break
            closing += 1
        if closing >= length or closing + 1 >= length or content[closing + 1] != "(":
            cursor = opening + 1
            continue

        index = closing + 2
        depth = 1
        in_angle = False
        while index < length:
            character = content[index]
            if character == "\\":
                index += 2
                continue
            if character == "<" and depth == 1:
                in_angle = True
            elif character == ">" and in_angle:
                in_angle = False
            elif not in_angle and character == "(":
                depth += 1
            elif not in_angle and character == ")":
                depth -= 1
                if depth == 0:
                    number = line_number(content, opening)
                    if number not in fenced:
                        link = MarkdownLink(
                            content[opening + 1 : closing],
                            content[closing + 2 : index],
                            opening,
                        )
                        found.append(link)
                    cursor = index + 1
                    break
            index += 1
        else:
            cursor = opening + 1

    reference_pattern = re.compile(r"\[([^\]\n]+)\]\[([^\]\n]*)\]")
    for match in reference_pattern.finditer(content):
        number = line_number(content, match.start())
        if number in fenced:
            continue
        key_text = match.group(2) or match.group(1)
        key = " ".join(key_text.split()).casefold()
        destination = definitions.get(key, "")
        found.append(
            MarkdownLink(
                match.group(1),
                destination,
                match.start(),
                unresolved_reference=not bool(destination),
            )
        )

    for link in sorted(found, key=lambda item: item.offset):
        yield link, line_number(content, link.offset)


def normalize_link_destination(link: str) -> str:
    value = link.strip()
    if value.startswith("<"):
        closing = value.find(">")
        if closing != -1:
            value = value[1:closing]
    else:
        # Unescaped spaces in a destination require angle brackets. Outside
        # angle brackets, whitespace can introduce an optional Markdown title.
        value = re.split(r"""\s+(?=["'(])""", value, maxsplit=1)[0]
    value = re.sub(r"\\([\\()<> ])", r"\1", value)
    return unquote(value)


def is_external_link(link: str) -> bool:
    normalized = normalize_link_destination(link)
    return normalized.startswith(
        ("http://", "https://", "mailto:", "#")
    ) or "://" in normalized


def resolve_link(filepath: Path, link: str) -> Path:
    normalized = normalize_link_destination(link)
    path_part = normalized.split("#", 1)[0].split("?", 1)[0]
    if path_part.startswith("/"):
        return (WIKI_ROOT / path_part.lstrip("/")).resolve()
    return (filepath.parent / path_part).resolve()


def check_markdown_links(content: str, filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    rel = relative_wiki(filepath)
    for match, number in markdown_links(content):
        link = match.destination.strip()
        if match.unresolved_reference:
            issues.append(
                Issue(
                    "P0",
                    rel,
                    number,
                    f"引用式链接未定义: '[{match.label}]'",
                )
            )
            continue
        if not link:
            issues.append(Issue("P0", rel, number, f"空链接: '[{match.label}]()'"))
            continue
        if is_external_link(link):
            continue
        target = resolve_link(filepath, link)
        try:
            target.relative_to(KB_ROOT)
        except ValueError:
            issues.append(Issue("P0", rel, number, f"链接越出知识库根目录: '{link}'"))
            continue
        if not target.exists():
            issues.append(Issue("P0", rel, number, f"断链: '{link}' → 目标不存在"))
    return issues


def linked_targets(content: str, filepath: Path) -> set[Path]:
    targets: set[Path] = set()
    for match, _ in markdown_links(content):
        link = match.destination.strip()
        if match.unresolved_reference or not link or is_external_link(link):
            continue
        targets.add(resolve_link(filepath, link))
    return targets


def check_index_structure() -> list[Issue]:
    issues: list[Issue] = []
    root_index = WIKI_ROOT / "index.md"
    if not root_index.is_file():
        issues.append(Issue("P0", ".", None, "WIKI 根目录缺少 index.md"))

    for directory in sorted(path for path in WIKI_ROOT.rglob("*") if path.is_dir()):
        if directory.name.startswith(".") or not list(directory.glob("*.md")):
            continue
        expected = directory / f"{directory.name}_index.md"
        if not expected.exists():
            issues.append(
                Issue(
                    "P0",
                    relative_wiki(directory),
                    None,
                    f"目录缺少索引: {expected.name}",
                )
            )

    index_files = sorted(WIKI_ROOT.rglob("*_index.md"))
    if root_index.is_file():
        index_files.insert(0, root_index)

    for index_file in index_files:
        try:
            content = index_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(Issue("P0", relative_wiki(index_file), None, f"读取失败: {exc}"))
            continue

        targets = linked_targets(content, index_file)
        expected_targets: list[tuple[Path, str]] = []
        for sibling in sorted(index_file.parent.glob("*.md")):
            if sibling == index_file or sibling.name == "log.md":
                continue
            expected_targets.append((sibling.resolve(), sibling.name))
        for child in sorted(
            path
            for path in index_file.parent.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ):
            child_index = child / f"{child.name}_index.md"
            if child_index.exists():
                expected_targets.append(
                    (child_index.resolve(), str(child_index.relative_to(index_file.parent)))
                )

        for target, label in expected_targets:
            if target not in targets:
                issues.append(
                    Issue(
                        "P2",
                        relative_wiki(index_file),
                        None,
                        f"索引未以链接覆盖: '{label}'",
                    )
                )
    return issues


def table_pipe_positions(line: str) -> list[int]:
    positions: list[int] = []
    index = 0
    code_delimiter = 0
    while index < len(line):
        character = line[index]
        if character == "`":
            run = 1
            while index + run < len(line) and line[index + run] == "`":
                run += 1
            if code_delimiter == 0:
                code_delimiter = run
            elif code_delimiter == run:
                code_delimiter = 0
            index += run
            continue
        if character == "|" and code_delimiter == 0:
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                positions.append(index)
        index += 1
    return positions


def column_count(line: str) -> int:
    stripped = line.strip()
    positions = table_pipe_positions(stripped)
    if not positions:
        return 1
    count = len(positions) + 1
    if positions[0] == 0:
        count -= 1
    if positions[-1] == len(stripped) - 1:
        count -= 1
    return count


def safe_leading_pipe_candidate(line: str) -> Optional[str]:
    if line.startswith("|||"):
        return "|" + line[3:]
    if line.startswith("|| |"):
        return line[1:]
    return None


def valid_separator_row(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return False
    cells = stripped[1:-1].split("|")
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.strip()) is not None for cell in cells
    )


def check_table_format(content: str, filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    rel = relative_wiki(filepath)
    lines = content.splitlines()
    fenced = fenced_lines(content)
    index = 0
    while index + 1 < len(lines):
        if index + 1 in fenced or index + 2 in fenced:
            index += 1
            continue
        header = lines[index].strip()
        separator = lines[index + 1].strip()
        looks_like_separator = re.fullmatch(r"\|[|:\- ]+\|", separator) is not None
        if (
            header.startswith("|")
            and header.endswith("|")
            and looks_like_separator
        ):
            if not valid_separator_row(separator):
                issues.append(
                    Issue(
                        "P2",
                        rel,
                        index + 2,
                        "表格分隔行每列至少需要三根横线",
                    )
                )
                index += 2
                continue
            expected = column_count(separator)
            if column_count(header) != expected:
                candidate = safe_leading_pipe_candidate(header)
                if candidate is not None and column_count(candidate) == expected:
                    issues.append(
                        Issue(
                            "P2",
                            rel,
                            index + 1,
                            f"表格行首疑似多一根竖线: {header[:80]}",
                        )
                    )
                else:
                    issues.append(
                        Issue("P2", rel, index + 1, "表头与分隔行列数不一致")
                    )
            cursor = index + 2
            while cursor < len(lines):
                if cursor + 1 in fenced:
                    break
                row = lines[cursor].strip()
                if not row.startswith("|") or not row.endswith("|"):
                    break
                if column_count(row) != expected:
                    candidate = safe_leading_pipe_candidate(row)
                    if candidate is not None and column_count(candidate) == expected:
                        issues.append(
                            Issue(
                                "P2",
                                rel,
                                cursor + 1,
                                f"表格行首疑似多一根竖线: {row[:80]}",
                            )
                        )
                    else:
                        issues.append(
                            Issue(
                                "P2",
                                rel,
                                cursor + 1,
                                f"表格数据行列数与表头不一致: {row[:80]}",
                            )
                        )
                cursor += 1
            index = cursor
        else:
            index += 1
    return issues


def check_line_number_pollution(content: str, filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    fenced = fenced_lines(content)
    for number, line in enumerate(content.splitlines(), 1):
        if number in fenced:
            continue
        if re.match(r"^\s*[0-9]{2,6}\|", line):
            issues.append(
                Issue(
                    "P0",
                    relative_wiki(filepath),
                    number,
                    f"疑似误粘贴读取行号前缀: {line.strip()[:80]}",
                )
            )
    return issues


def check_hard_process_noise(content: str, filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    for number, line in enumerate(content.splitlines(), 1):
        for phrase in HARD_PROCESS_NOISE:
            if phrase in line:
                issues.append(
                    Issue(
                        "P1",
                        relative_wiki(filepath),
                        number,
                        f"WIKI 含维护过程噪声: '{phrase}'",
                    )
                )
    return issues


def run_checks() -> list[Issue]:
    issues = check_index_structure()
    for filepath in sorted(WIKI_ROOT.rglob("*.md")):
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(Issue("P0", relative_wiki(filepath), None, f"读取失败: {exc}"))
            continue
        if filepath.name == "log.md":
            continue
        frontmatter, fm_issues = parse_frontmatter(content, filepath)
        issues.extend(fm_issues)
        issues.extend(check_sources(frontmatter, filepath))
        issues.extend(check_markdown_links(content, filepath))
        issues.extend(check_table_format(content, filepath))
        issues.extend(check_line_number_pollution(content, filepath))
        issues.extend(check_hard_process_noise(content, filepath))
    return issues


def safe_fix_tables(issues: list[Issue]) -> int:
    by_file: dict[str, set[int]] = defaultdict(set)
    for issue in issues:
        if issue.line and "表格行首疑似多一根竖线" in issue.msg:
            by_file[issue.file].add(issue.line)

    changed = 0
    for rel, line_numbers in by_file.items():
        filepath = WIKI_ROOT / rel
        lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)
        file_changed = False
        for number in line_numbers:
            original = lines[number - 1]
            if original.startswith("|||"):
                lines[number - 1] = "|" + original[3:]
                file_changed = True
            elif original.startswith("|| |"):
                lines[number - 1] = original[1:]
                file_changed = True
        if file_changed:
            filepath.write_text("".join(lines), encoding="utf-8")
            changed += 1
    return changed


def parse_iso_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(scalar_value(value))
    except (TypeError, ValueError):
        return None


def run_audit() -> dict[str, list[str]]:
    findings: dict[str, list[str]] = defaultdict(list)
    metadata: dict[Path, Frontmatter] = {}
    content_cache: dict[Path, str] = {}

    for filepath in sorted(WIKI_ROOT.rglob("*.md")):
        if filepath.name == "log.md":
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            # The deterministic pass already reports this as a blocker.
            continue
        content_cache[filepath] = content
        frontmatter, _ = parse_frontmatter(content, filepath)
        if frontmatter:
            metadata[filepath] = frontmatter
            body = content.splitlines()[frontmatter.end_line :]
        else:
            body = content.splitlines()
        body_text = "\n".join(body)

        for category, markers in AUDIT_MARKERS.items():
            hits = sorted({marker for marker in markers if marker in body_text})
            if hits:
                findings[category].append(
                    f"{relative_wiki(filepath)}: {', '.join(hits)}"
                )

        meaningful = [
            line
            for line in body
            if line.strip()
            and not line.strip().startswith(("#", "> 菜单路径", "> URL"))
        ]
        meaningful_chars = len("".join(line.strip() for line in meaningful))
        doc_type = scalar_value(frontmatter.fields.get("type", "")) if frontmatter else ""
        external_placeholder = "外部" in body_text and "不维护" in body_text
        if (
            doc_type != "index"
            and not external_placeholder
            and len(meaningful) < 10
            and meaningful_chars < 160
        ):
            findings["正文偏短"].append(
                f"{relative_wiki(filepath)}: 有效正文约 {len(meaningful)} 行/{meaningful_chars} 字"
            )

    for filepath, frontmatter in metadata.items():
        if scalar_value(frontmatter.fields.get("type", "")) != "index":
            continue
        index_date = parse_iso_date(frontmatter.fields.get("updated", ""))
        if index_date:
            descendant_dates = [
                parse_iso_date(other.fields.get("updated", ""))
                for child, other in metadata.items()
                if child != filepath and filepath.parent in child.parents
            ]
            newest = max((item for item in descendant_dates if item), default=None)
            if newest and newest > index_date:
                findings["索引更新时间滞后"].append(
                    f"{relative_wiki(filepath)}: {index_date} < 子文档 {newest}"
                )

        content = content_cache.get(filepath, "")
        progress_hits: list[str] = []
        for number, line in enumerate(content.splitlines(), 1):
            markers = [marker for marker in INDEX_PROGRESS_MARKERS if marker in line]
            if markers:
                progress_hits.append(f"{relative_wiki(filepath)}:{number}: {', '.join(markers)}")
        findings["Index 临时进度标记"].extend(progress_hits)

    statuses: dict[Path, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    status_indexes = sorted(WIKI_ROOT.rglob("*_index.md"))
    root_index = WIKI_ROOT / "index.md"
    if root_index.is_file():
        status_indexes.insert(0, root_index)
    for index_file in status_indexes:
        content = content_cache.get(index_file)
        if content is None:
            continue
        lines = content.splitlines()
        for match, number in markdown_links(content):
            link = match.destination.strip()
            if not link or is_external_link(link):
                continue
            line = lines[number - 1]
            status = (
                "complete"
                if "✅" in line
                else "partial"
                if any(marker in line for marker in ("🚧", "待记录", "记录中", "⬜"))
                else "unknown"
            )
            if status != "unknown":
                statuses[resolve_link(index_file, link)][status].append(
                    f"{relative_wiki(index_file)}:{number}"
                )
    for target, values in statuses.items():
        if values.get("complete") and values.get("partial"):
            findings["索引状态冲突"].append(
                f"{relative_wiki(target)}: complete={values['complete']}, "
                f"partial={values['partial']}"
            )

    return {key: value for key, value in findings.items() if value}


def check_initialization_placeholders() -> list[Issue]:
    issues: list[Issue] = []
    reported_paths: set[Path] = set()
    bootstrap = KB_ROOT / "BOOTSTRAP_ONCE.md"
    if bootstrap.exists():
        issues.append(
            Issue(
                "P3",
                relative_kb(bootstrap),
                None,
                "首次建库完成后应删除或归档一次性清单",
            )
        )
        reported_paths.add(bootstrap)

    # Only scan files that become real business configuration or knowledge.
    # Skills, README files, sharing guidance, and query fixtures intentionally
    # retain fictional examples after initialization.
    content_files = [KB_ROOT / "AGENTS.md", *sorted(WIKI_ROOT.rglob("*.md"))]
    for filepath in content_files:
        if not filepath.is_file():
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(
                Issue("P0", relative_kb(filepath), None, f"文件读取失败: {exc}")
            )
            continue
        for number, line in enumerate(content.splitlines(), 1):
            hits = [marker for marker in INITIALIZATION_MARKERS if marker in line]
            if hits:
                issues.append(
                    Issue(
                        "P3",
                        relative_kb(filepath),
                        number,
                        f"真实建库前应替换模板占位内容: {', '.join(hits)}",
                    )
                )
                reported_paths.add(filepath)
                break

    # Content may already be edited while sample paths remain. Check names in
    # the published WIKI and screenshot evidence tree without inspecting
    # reusable RAW templates or instructional prose.
    path_roots = (WIKI_ROOT, RAW_ROOT / "截图")
    reported_name_roots: set[Path] = set()
    for root in path_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*"), key=lambda item: (len(item.parts), str(item))):
            if path in reported_paths:
                continue
            if any(parent in reported_name_roots for parent in path.parents):
                continue
            relative = path.relative_to(KB_ROOT).as_posix()
            hits = [marker for marker in INITIALIZATION_MARKERS if marker in relative]
            if not hits:
                continue
            issues.append(
                Issue(
                    "P3",
                    relative_kb(path),
                    None,
                    f"真实建库前应替换模板占位路径: {', '.join(hits)}",
                )
            )
            reported_paths.add(path)
            reported_name_roots.add(path)

    for filepath in content_files:
        if not filepath.is_file():
            continue
        try:
            content = filepath.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        frontmatter, _ = parse_frontmatter(content, filepath)
        if frontmatter is None:
            continue
        for source, number in frontmatter.source_entries:
            source_path = source.split("#", 1)[0].strip()
            if source_path in INITIALIZATION_SAMPLE_ASSETS:
                issues.append(
                    Issue(
                        "P3",
                        relative_kb(filepath),
                        number,
                        f"真实建库前应替换模板示例证据: {source_path}",
                    )
                )
    return issues


def check_share_artifacts() -> list[Issue]:
    issues: list[Issue] = []
    for path in sorted(KB_ROOT.rglob("*")):
        relative_parts = path.relative_to(KB_ROOT).parts
        if ".git" in relative_parts:
            continue
        if path == KB_ROOT / ".work":
            issues.append(
                Issue(
                    "P2",
                    relative_kb(path),
                    None,
                    "分享包不应包含临时工作层 .work",
                )
            )
            continue
        if ".work" in relative_parts:
            continue
        if (
            path.name in SHARE_ARTIFACT_NAMES
            or path.suffix in {".bak", ".pyc", ".swo", ".swp", ".tmp"}
            or path.name.endswith("~")
        ):
            issues.append(
                Issue(
                    "P2",
                    relative_kb(path),
                    None,
                    "分享前应清理本地编辑器、系统或运行时杂文件",
                )
            )
    return issues


def load_sensitive_terms(args: argparse.Namespace) -> list[str]:
    terms = [term.strip() for term in args.sensitive_term if term.strip()]
    if args.sensitive_file:
        try:
            for line in args.sensitive_file.expanduser().read_text(
                encoding="utf-8-sig"
            ).splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    terms.append(stripped)
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(
                f"Failed to read sensitive file: {args.sensitive_file}: {exc}"
            ) from exc
    return list(dict.fromkeys(terms))


def iter_share_text_files():
    for filepath in sorted(KB_ROOT.rglob("*")):
        if not filepath.is_file():
            continue
        if (
            filepath.suffix.lower() not in SHARE_TEXT_SUFFIXES
            and filepath.name not in SHARE_TEXT_NAMES
            and not filepath.name.startswith((".env.", "Dockerfile."))
        ):
            continue
        relative_parts = filepath.relative_to(KB_ROOT).parts
        if any(part in {".git", ".work", ".idea", "__pycache__"} for part in relative_parts):
            continue
        yield filepath


def check_sensitive_terms(terms: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    if not terms:
        return issues
    for path in sorted(KB_ROOT.rglob("*")):
        relative_parts = path.relative_to(KB_ROOT).parts
        if any(part in {".git", ".work"} for part in relative_parts):
            continue
        for term in terms:
            if term in path.name:
                issues.append(
                    Issue(
                        "P1",
                        relative_kb(path),
                        None,
                        f"文件或目录名命中用户提供的敏感词: {term}",
                    )
                )

    for filepath in iter_share_text_files():
        try:
            raw = filepath.read_bytes()
        except OSError as exc:
            issues.append(
                Issue("P0", relative_kb(filepath), None, f"文件读取失败: {exc}")
            )
            continue
        content: Optional[str] = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                content = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if content is None:
            issues.append(
                Issue(
                    "P1",
                    relative_kb(filepath),
                    None,
                    "文本文件无法按 UTF-8 或 GB18030 解码，敏感词扫描未完成",
                )
            )
            continue
        for number, line in enumerate(content.splitlines(), 1):
            for term in terms:
                if term in line:
                    issues.append(
                        Issue(
                            "P1",
                            relative_kb(filepath),
                            number,
                            f"命中用户提供的敏感词: {term}",
                        )
                    )
    return issues


def print_issues(issues: list[Issue]) -> None:
    if not issues:
        print("PASS: deterministic checks found no publication blockers.")
        return

    print(f"FAIL: {len(issues)} issue(s) found.\n")
    labels = {
        "P0": "P0 blocking",
        "P1": "P1 serious",
        "P2": "P2 format/index/share",
        "P3": "P3 initialization",
    }
    for severity in ("P0", "P1", "P2", "P3"):
        group = sorted(
            (item for item in issues if item.severity == severity),
            key=lambda item: (item.file, item.line or 0, item.msg),
        )
        if not group:
            continue
        print(f"{labels[severity]} ({len(group)})")
        for issue in group:
            location = f":{issue.line}" if issue.line else ""
            print(f"  {issue.file}{location} - {issue.msg}")
        print()


def print_audit(findings: dict[str, list[str]]) -> None:
    print("\nAUDIT: non-blocking content-quality findings")
    if not findings:
        print("  No maturity, process-language, freshness, or status findings.")
        return
    for category in sorted(findings):
        items = findings[category]
        print(f"\n  {category}: {len(items)}")
        for item in items[:12]:
            print(f"  - {item}")
        if len(items) > 12:
            print(f"  - ... {len(items) - 12} more")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Business knowledge-base publication lint and non-blocking audit"
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="Knowledge-base root or WIKI directory; default is discovered from this script.",
    )
    parser.add_argument(
        "--audit",
        action="store_true",
        help="Add non-blocking maturity, process-language, freshness, and status findings.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix only confirmed extra leading table pipes, then rerun all checks.",
    )
    parser.add_argument(
        "--strict-init",
        action="store_true",
        help="Check for template placeholders left in an initialized real knowledge base.",
    )
    parser.add_argument(
        "--share-check",
        action="store_true",
        help="Check local editor, system, and runtime artifacts before sharing.",
    )
    parser.add_argument(
        "--sensitive-term",
        action="append",
        default=[],
        help="Sensitive term to scan for; may be repeated.",
    )
    parser.add_argument(
        "--sensitive-file",
        type=Path,
        help="File containing sensitive terms, one per line.",
    )
    return parser


def main() -> int:
    global KB_ROOT, WIKI_ROOT, RAW_ROOT
    args = build_parser().parse_args()
    discovered = normalize_kb_root(args.root) if args.root else discover_kb_root()
    if discovered is None:
        requested = args.root if args.root else Path(__file__).resolve()
        print(f"Invalid knowledge-base root near: {requested}", file=sys.stderr)
        return 2

    KB_ROOT = discovered
    WIKI_ROOT = KB_ROOT / "WIKI"
    RAW_ROOT = KB_ROOT / "RAW_SOURCES"

    try:
        sensitive_terms = load_sensitive_terms(args)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    md_files = sorted(WIKI_ROOT.rglob("*.md"))
    print(f"Scanned: {WIKI_ROOT}")
    print(f"Markdown files: {len(md_files)}")

    issues = run_checks()
    if args.fix:
        changed = safe_fix_tables(issues)
        print(f"Fixed safe table-pipe issues in {changed} file(s); rerunning checks.")
        issues = run_checks()
    if args.strict_init:
        issues.extend(check_initialization_placeholders())
    if args.share_check:
        issues.extend(check_share_artifacts())
    issues.extend(check_sensitive_terms(sensitive_terms))

    print_issues(issues)
    if args.audit:
        print_audit(run_audit())
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
