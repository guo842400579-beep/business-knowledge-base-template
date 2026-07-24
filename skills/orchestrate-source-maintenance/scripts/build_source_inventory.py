#!/usr/bin/env python3
"""Build read-only source and WIKI navigation inventories.

The output is a candidate map, not a business conclusion. Existing generated
files are not overwritten unless ``--force`` is supplied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


SKIP_DIRS = {
    ".git",
    ".idea",
    ".gradle",
    ".next",
    ".venv",
    ".work",
    "__pycache__",
    "build",
    "dist",
    "examples",
    "fixtures",
    "node_modules",
    "spec",
    "specs",
    "target",
    "test",
    "tests",
    "vendor",
}

DEFAULT_EXTENSIONS = {
    ".gql",
    ".graphql",
    ".java",
    ".kt",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rb",
    ".php",
    ".cs",
    ".rs",
    ".proto",
    ".sql",
}

REPOSITORY_FIELDS = [
    "system",
    "repository",
    "path",
    "branch",
    "commit",
    "worktree",
    "worktree_fingerprint",
    "total_files",
    "source_files",
    "candidate_entrypoints",
    "profile",
]

ENTRY_FIELDS = [
    "entry_id",
    "system",
    "repository",
    "module",
    "category",
    "symbol",
    "routes",
    "relative_path",
    "classification",
    "linked_wiki_rows",
    "last_verified_commit",
    "last_verified_worktree_fingerprint",
    "notes",
]

COVERAGE_FIELDS = [
    "row_id",
    "coverage_kind",
    "system",
    "wiki_path",
    "title",
    "object_type",
    "source_mapping_path",
    "mapping_exists",
    "analysis_status",
    "priority",
    "source_repositories",
    "candidate_entrypoints",
    "page_evidence_status",
    "conclusion_status",
    "assigned_batch",
    "last_verified_commit",
    "notes",
]

CHAIN_FIELDS = [
    "chain_id",
    "wiki_path",
    "title",
    "participating_objects",
    "source_entrypoints",
    "status",
    "last_verified_commits",
    "notes",
]

FINDING_FIELDS = [
    "finding_id",
    "coverage_row_id",
    "business_conclusion",
    "target_wiki_path",
    "target_heading",
    "fusion_action",
    "old_wording_action",
    "source_mapping_path",
    "blocker",
    "review_notes",
    "status",
]

ENTRY_PATTERNS = (
    (
        "controller-api-router",
        re.compile(
            r"(Controller|Api|API|Router|Routes?|Endpoint|Resource|ViewSet)$", re.I
        ),
    ),
    ("graphql-resolver", re.compile(r"(Resolver|Mutation|QueryRoot)$", re.I)),
    ("facade", re.compile(r"Facade(?:Impl)?$", re.I)),
    ("handler-process", re.compile(r"(Handler|Process|Processor)$", re.I)),
    ("command-query-usecase", re.compile(r"(Command|Query|UseCase|Interactor)$", re.I)),
    ("validator", re.compile(r"Validator$", re.I)),
    ("rule-strategy", re.compile(r"(Rule|Strategy|Policy)$", re.I)),
    ("repository-mapper", re.compile(r"(Repository|Repo|Mapper|DAO)$", re.I)),
    ("consumer-listener", re.compile(r"(Consumer|Listener|Subscriber)$", re.I)),
    ("producer-publisher", re.compile(r"(Producer|Publisher)$", re.I)),
    ("job-task", re.compile(r"(Job|Task|Scheduler|Cron)$", re.I)),
    ("workflow-saga", re.compile(r"(Workflow|Saga|Orchestrator)$", re.I)),
    ("service", re.compile(r"Service(?:Impl)?$", re.I)),
    ("enum-model-type", re.compile(r"(Enum|Model|Entity|DTO|VO|Type|Types)$", re.I)),
)

SPRING_ROUTE = re.compile(
    r"@(?:RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)"
    r"\s*(?:\((?P<args>[^)]*)\))?",
    re.MULTILINE,
)
DECORATOR_ROUTE = re.compile(
    r"@(?:app|router|blueprint)\.(?:get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']",
    re.I,
)
CALL_ROUTE = re.compile(
    r"\.(?:get|post|put|delete|patch)\(\s*[\"'](/[^\"']*)[\"']",
    re.I,
)
STRING_LITERAL = re.compile(r"[\"']([^\"']+)[\"']")
CONTENT_ENTRY_PATTERNS = (
    (
        "controller-api-router",
        {".rs"},
        re.compile(
            r"(?:Router::new|\.route\s*\(|#\[(?:get|post|put|delete|patch)\b|"
            r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+/)",
            re.I,
        ),
    ),
    (
        "controller-api-router",
        {".js", ".jsx", ".php", ".py", ".rb", ".ts", ".tsx"},
        re.compile(
            r"(?:@(?:app|router|blueprint)\.(?:get|post|put|delete|patch)\s*\(|"
            r"\.(?:get|post|put|delete|patch)\(\s*[\"']/)",
            re.I,
        ),
    ),
    (
        "graphql-resolver",
        {".gql", ".graphql", ".java", ".js", ".jsx", ".kt", ".ts", ".tsx"},
        re.compile(r"(?:@(?:Resolver|Query|Mutation)\b|extend\s+type\s+(?:Query|Mutation))"),
    ),
    (
        "proto-service",
        {".proto"},
        re.compile(r"(?m)^\s*service\s+[A-Za-z_][A-Za-z0-9_]*\s*\{"),
    ),
    (
        "stored-procedure",
        {".sql"},
        re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION)\b", re.I),
    ),
)
DEFAULT_COVERAGE_ROOTS = ("功能模块", "概念", "操作流程")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        metavar="SYSTEM=PATH",
        help="Repeat for each source repository.",
    )
    parser.add_argument("--wiki-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--coverage-root",
        action="append",
        default=[],
        help=(
            "Path relative to WIKI root to inventory; repeat as needed. "
            "Defaults to 功能模块, 概念, and 操作流程."
        ),
    )
    parser.add_argument(
        "--feature-root",
        help="Deprecated single-root alias for --coverage-root.",
    )
    parser.add_argument(
        "--mapping-root",
        default="源码映射",
        help="Path relative to WIKI root for mirrored source mappings.",
    )
    parser.add_argument(
        "--profile",
        choices=("generic", "spring-java"),
        default="generic",
        help="Optional route-extraction profile. Classification remains heuristic.",
    )
    parser.add_argument(
        "--include-ext",
        action="append",
        default=[],
        help="Source extension to include; repeat as needed, for example .java.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite generated inventories; may discard manual triage.",
    )
    return parser.parse_args()


def parse_repo(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError(f"Invalid --repo value {value!r}; expected SYSTEM=PATH")
    system, raw_path = value.split("=", 1)
    path = Path(raw_path).expanduser().resolve()
    if not system.strip() or not path.is_dir():
        raise ValueError(f"Invalid repository {value!r}")
    return system.strip(), path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.stdout if result.returncode == 0 else b""


def worktree_fingerprint(repo: Path) -> str:
    digest = hashlib.sha256()
    digest.update(git(repo, "status", "--short").encode("utf-8"))
    digest.update(b"\0INDEX\0")
    digest.update(git(repo, "ls-files", "--stage").encode("utf-8"))
    digest.update(b"\0CACHED-DIFF\0")
    digest.update(git_bytes(repo, "diff", "--binary", "--cached"))
    digest.update(b"\0WORKTREE-DIFF\0")
    digest.update(git_bytes(repo, "diff", "--binary"))
    untracked = [
        value
        for value in git_bytes(
            repo, "ls-files", "-z", "--others", "--exclude-standard"
        ).split(b"\0")
        if value
    ]
    for relative_bytes in sorted(untracked):
        digest.update(relative_bytes)
        digest.update(b"\0")
        path = repo / os.fsdecode(relative_bytes)
        if path.is_file():
            try:
                with path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError:
                digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.hexdigest()


def git_metadata(repo: Path) -> tuple[str, str, str, str]:
    if git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        return "", "", "not-git", ""
    branch = git(repo, "branch", "--show-current")
    commit = git(repo, "rev-parse", "HEAD")
    worktree = "dirty" if git(repo, "status", "--short") else "clean"
    fingerprint = worktree_fingerprint(repo) if worktree == "dirty" else ""
    return branch, commit, worktree, fingerprint


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        yield path


def module_name(relative_path: Path) -> str:
    return relative_path.parts[0] if len(relative_path.parts) > 1 else "root"


def relative_if_within(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def symbol_name(path: Path) -> str:
    name = path.stem
    if name in {"index", "__init__", "main", "app", "routes", "router"}:
        parent = path.parent.name
        return f"{parent}-{name}" if parent else name
    return name


def entry_category(path: Path) -> str | None:
    symbol = symbol_name(path)
    for category, pattern in ENTRY_PATTERNS:
        if pattern.search(symbol):
            return category
    if path.stem.lower() in {"routes", "router", "api", "urls", "views"}:
        return "controller-api-router"
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")[:500_000]
    except OSError:
        return None
    for category, extensions, pattern in CONTENT_ENTRY_PATTERNS:
        if path.suffix.lower() in extensions and pattern.search(content):
            return category
    return None


def extract_routes(path: Path, profile: str) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    routes: list[str] = []
    if profile == "spring-java":
        for match in SPRING_ROUTE.finditer(content):
            for value in STRING_LITERAL.findall(match.group("args") or ""):
                if value.startswith("/") and value not in routes:
                    routes.append(value)
    for pattern in (DECORATOR_ROUTE, CALL_ROUTE):
        for match in pattern.finditer(content):
            value = match.group(1)
            if value.startswith("/") and value not in routes:
                routes.append(value)
    return ";".join(routes[:50])


def read_title_and_type(path: Path) -> tuple[str, str]:
    head = path.read_text(encoding="utf-8", errors="ignore")[:5000]
    title = re.search(r"(?m)^title:\s*[\"']?(.+?)[\"']?\s*$", head)
    doc_type = re.search(r"(?m)^type:\s*([a-z_-]+)\s*$", head)
    return (
        title.group(1).strip() if title else path.stem,
        doc_type.group(1).strip() if doc_type else "unknown",
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def wiki_snapshot(wiki_root: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    files = sorted(wiki_root.rglob("*.md"))
    for path in files:
        relative = path.relative_to(wiki_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    repo_root = wiki_root.parent
    _, commit, worktree, fingerprint = git_metadata(repo_root)
    return {
        "wiki_root": str(wiki_root),
        "markdown_files": len(files),
        "wiki_snapshot_sha256": digest.hexdigest(),
        "knowledge_base_vcs": "git" if worktree != "not-git" else "none",
        "knowledge_base_commit": commit,
        "knowledge_base_worktree": worktree,
        "knowledge_base_worktree_fingerprint": fingerprint,
    }


def main() -> int:
    args = parse_args()
    try:
        repos = [parse_repo(value) for value in args.repo]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    wiki_root = args.wiki_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    mapping_root = (wiki_root / args.mapping_root).resolve()
    if args.coverage_root and args.feature_root:
        raise SystemExit("Use --coverage-root or --feature-root, not both")
    coverage_values = (
        args.coverage_root
        or ([args.feature_root] if args.feature_root else list(DEFAULT_COVERAGE_ROOTS))
    )
    coverage_roots = list(
        dict.fromkeys((wiki_root / value).resolve() for value in coverage_values)
    )
    extensions = {
        value if value.startswith(".") else f".{value}"
        for value in (args.include_ext or DEFAULT_EXTENSIONS)
    }

    for path in [*coverage_roots, mapping_root]:
        try:
            path.relative_to(wiki_root)
        except ValueError as exc:
            raise SystemExit(f"Coverage and mapping roots must stay inside WIKI: {path}") from exc

    for index, left in enumerate(coverage_roots):
        for right in coverage_roots[index + 1 :]:
            try:
                right.relative_to(left)
                overlap = True
            except ValueError:
                try:
                    left.relative_to(right)
                    overlap = True
                except ValueError:
                    overlap = False
            if overlap:
                raise SystemExit(
                    f"Coverage roots must not overlap: {left} / {right}"
                )

    missing_roots = [path for path in coverage_roots if not path.is_dir()]
    if not wiki_root.is_dir() or missing_roots:
        missing = ", ".join(str(path) for path in missing_roots)
        raise SystemExit(f"Missing WIKI or coverage root: {wiki_root} / {missing}")

    output_dir.mkdir(parents=True, exist_ok=True)
    generated_names = (
        "repository-inventory.csv",
        "source-entrypoints.csv",
        "wiki-coverage.csv",
        "cross-object-chains.csv",
        "semantic-findings.csv",
        "unmapped-entrypoints.csv",
        "wiki-snapshot.json",
    )
    existing = [output_dir / name for name in generated_names if (output_dir / name).exists()]
    if existing and not args.force:
        joined = ", ".join(str(path) for path in existing)
        raise SystemExit(f"Refusing to overwrite existing inventories without --force: {joined}")

    repository_rows: list[dict[str, object]] = []
    entry_rows: list[dict[str, object]] = []
    entry_counter = 1

    for system, repo in repos:
        files = list(iter_files(repo))
        source_files = [path for path in files if path.suffix.lower() in extensions]
        categorized: list[tuple[Path, str]] = []
        for path in source_files:
            category = entry_category(path)
            if category:
                categorized.append((path, category))

        branch, commit, worktree, fingerprint = git_metadata(repo)
        repository_rows.append(
            {
                "system": system,
                "repository": repo.name,
                "path": str(repo),
                "branch": branch,
                "commit": commit,
                "worktree": worktree,
                "worktree_fingerprint": fingerprint,
                "total_files": len(files),
                "source_files": len(source_files),
                "candidate_entrypoints": len(categorized),
                "profile": args.profile,
            }
        )

        for path, category in sorted(categorized, key=lambda item: str(item[0])):
            relative = path.relative_to(repo)
            entry_rows.append(
                {
                    "entry_id": f"SRC-{entry_counter:05d}",
                    "system": system,
                    "repository": repo.name,
                    "module": module_name(relative),
                    "category": category,
                    "symbol": symbol_name(path),
                    "routes": extract_routes(path, args.profile),
                    "relative_path": relative.as_posix(),
                    "classification": "unassigned",
                    "linked_wiki_rows": "",
                    "last_verified_commit": commit,
                    "last_verified_worktree_fingerprint": fingerprint,
                    "notes": "",
                }
            )
            entry_counter += 1

    coverage_rows: list[dict[str, object]] = []
    coverage_counter = 1
    feature_base = (wiki_root / "功能模块").resolve()
    concept_base = (wiki_root / "概念").resolve()
    process_base = (wiki_root / "操作流程").resolve()
    custom_feature_root = (
        (wiki_root / args.feature_root).resolve() if args.feature_root else None
    )
    for coverage_root in coverage_roots:
        feature_scope = relative_if_within(coverage_root, feature_base)
        concept_scope = relative_if_within(coverage_root, concept_base)
        process_scope = relative_if_within(coverage_root, process_base)
        if feature_scope is not None:
            coverage_kind = "功能模块"
            mapping_base = feature_base
            mapping_namespace = None
        elif concept_scope is not None:
            coverage_kind = "概念"
            mapping_base = concept_base
            mapping_namespace = Path("概念")
        elif process_scope is not None:
            coverage_kind = "操作流程"
            mapping_base = process_base
            mapping_namespace = Path("操作流程")
        elif custom_feature_root and coverage_root == custom_feature_root:
            coverage_kind = coverage_root.relative_to(wiki_root).as_posix()
            mapping_base = custom_feature_root
            mapping_namespace = None
        else:
            coverage_kind = coverage_root.relative_to(wiki_root).as_posix()
            mapping_base = coverage_root
            mapping_namespace = Path(coverage_kind)

        for path in sorted(coverage_root.rglob("*.md")):
            relative = path.relative_to(coverage_root)
            title, object_type = read_title_and_type(path)
            mapping_relative = path.relative_to(mapping_base)
            is_feature = mapping_namespace is None
            system = (
                mapping_relative.parts[0]
                if is_feature and len(mapping_relative.parts) > 1
                else ""
            )
            if is_feature and path == mapping_base / f"{mapping_base.name}_index.md":
                mapping_path = mapping_root / f"{mapping_root.name}_index.md"
            elif is_feature:
                mapping_path = mapping_root / mapping_relative
            else:
                mapping_path = mapping_root / mapping_namespace / mapping_relative
            coverage_rows.append(
                {
                    "row_id": f"KB-{coverage_counter:04d}",
                    "coverage_kind": coverage_kind,
                    "system": system,
                    "wiki_path": path.relative_to(wiki_root.parent).as_posix(),
                    "title": title,
                    "object_type": object_type,
                    "source_mapping_path": mapping_path.relative_to(
                        wiki_root.parent
                    ).as_posix(),
                    "mapping_exists": "yes" if mapping_path.is_file() else "no",
                    "analysis_status": "untriaged",
                    "priority": "",
                    "source_repositories": "",
                    "candidate_entrypoints": "",
                    "page_evidence_status": "unknown",
                    "conclusion_status": "not-reviewed",
                    "assigned_batch": "",
                    "last_verified_commit": "",
                    "notes": "",
                }
            )
            coverage_counter += 1

    chain_rows: list[dict[str, object]] = []
    chain_counter = 1
    process_roots = [
        root
        for root in coverage_roots
        if relative_if_within(root, process_base) is not None
    ]
    for process_root in process_roots:
        process_pages = [
            path
            for path in sorted(process_root.rglob("*.md"))
            if not path.name.endswith("_index.md")
        ]
        for path in process_pages:
            title, _ = read_title_and_type(path)
            chain_rows.append(
                {
                    "chain_id": f"CHAIN-{chain_counter:04d}",
                    "wiki_path": path.relative_to(wiki_root.parent).as_posix(),
                    "title": title,
                    "participating_objects": "",
                    "source_entrypoints": "",
                    "status": "untriaged",
                    "last_verified_commits": "",
                    "notes": "",
                }
            )
            chain_counter += 1

    high_value_rows = [
        row
        for row in entry_rows
        if row["category"] not in {"repository-mapper", "enum-model-type"}
    ]
    write_csv(
        output_dir / "repository-inventory.csv",
        REPOSITORY_FIELDS,
        repository_rows,
    )
    write_csv(
        output_dir / "source-entrypoints.csv",
        ENTRY_FIELDS,
        entry_rows,
    )
    write_csv(
        output_dir / "wiki-coverage.csv",
        COVERAGE_FIELDS,
        coverage_rows,
    )
    write_csv(output_dir / "cross-object-chains.csv", CHAIN_FIELDS, chain_rows)
    write_csv(output_dir / "semantic-findings.csv", FINDING_FIELDS, [])
    write_csv(
        output_dir / "unmapped-entrypoints.csv",
        ENTRY_FIELDS,
        high_value_rows,
    )
    (output_dir / "wiki-snapshot.json").write_text(
        json.dumps(wiki_snapshot(wiki_root), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if not (output_dir / "batches.md").exists():
        (output_dir / "batches.md").write_text(
            "# 源码维护批次\n\n> 按覆盖矩阵安排批次，并在每批结束后更新恢复点。\n",
            encoding="utf-8",
        )
    if not (output_dir / "decisions.md").exists():
        (output_dir / "decisions.md").write_text(
            "# 范围与决策\n\n> 记录纳入、排除、冲突处理和范围调整理由。\n",
            encoding="utf-8",
        )

    print(
        f"Wrote {len(repository_rows)} repositories, {len(entry_rows)} candidate entrypoints, "
        f"{len(high_value_rows)} unmapped high-value candidates, "
        f"{len(coverage_rows)} WIKI objects, and {len(chain_rows)} cross-object chains "
        f"to {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
