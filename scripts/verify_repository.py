#!/usr/bin/env python3
"""Verify mechanically enforceable repository-governance invariants."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tomllib
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LEGACY_DOCUMENTATION_PATHS = {
    "architecture.txt",
    "architecture_realistic.md",
    "changelog_realistic.md",
    "delivery_summary.txt",
    "documentation_update_summary.md",
    "project_tracking.md",
    "readme_realistic.md",
    "status.md",
    "status.txt",
}
REQUIRED_DOCUMENTATION_PATHS = {
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/DEVELOPMENT.md",
    "docs/LIMITATIONS.md",
    "docs/RELEASE_PROCESS.md",
    "docs/ROADMAP.md",
    "docs/TESTING.md",
}
REQUIRED_CHECK_NAMES = {
    "ci-windows-py310",
    "ci-windows-py312",
    "ci-ubuntu-py312",
    "release-regressions",
    "repository-truth",
    "package-build-install",
    "dependency-review",
}
FORBIDDEN_TRACKED_COMPONENTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
}
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
ACTION_REFERENCE_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
JOB_IDENTIFIER_PATTERN = re.compile(r"^  ([a-z0-9][a-z0-9-]*):\s*$", re.MULTILINE)
FULL_SHA_ACTION_PATTERN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


class RepositoryVerificationError(RuntimeError):
    """Raised when one or more repository invariants fail."""


def run_git(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def repository_paths() -> list[PurePosixPath]:
    result = run_git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return [PurePosixPath(path) for path in result.stdout.split("\0") if path]


def read_repository_text(path: PurePosixPath) -> str:
    return REPOSITORY_ROOT.joinpath(*path.parts).read_text(encoding="utf-8-sig")


def _canonical_version() -> str:
    """Read the single source-of-truth version from ``core/_version.py`` statically."""
    version_module = REPOSITORY_ROOT / "core" / "_version.py"
    tree = ast.parse(version_module.read_text(encoding="utf-8"), filename=str(version_module))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                raise RepositoryVerificationError("core/_version.py __version__ must be a string")
            return value
    raise RepositoryVerificationError("core/_version.py does not define __version__")


def verify_version_truth(paths: set[str]) -> list[str]:
    """Validate the single canonical version source and its declared consumers.

    The application version is defined exactly once in ``core/_version.py``. Every
    other surface (packaging metadata, the runtime banner, the UI label/About box)
    must derive from it rather than repeat a literal string.
    """
    errors: list[str] = []
    pyproject_path = REPOSITORY_ROOT / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    project = pyproject["project"]

    try:
        version = _canonical_version()
    except RepositoryVerificationError as error:
        return [str(error)]

    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"core/_version.py __version__ is not a plain semantic version: {version}")

    if "version" in project:
        errors.append("pyproject.toml [project] must not pin a literal version; declare it dynamic")
    if "version" not in project.get("dynamic", []):
        errors.append('pyproject.toml [project].dynamic must include "version"')
    dynamic_version = (
        pyproject.get("tool", {}).get("setuptools", {}).get("dynamic", {}).get("version")
    )
    if dynamic_version != {"attr": "core._version.__version__"}:
        errors.append(
            "pyproject.toml [tool.setuptools.dynamic].version must be "
            '{attr = "core._version.__version__"}'
        )

    required_markers = {
        "core/__init__.py": ("from core._version import __version__",),
        "main.py": ("from core import __version__", "BATCHSTUDIO v{__version__}"),
        "ui/main_window.py": ("from core import __version__", 'f"v{__version__}"'),
        "CHANGELOG.md": (f"## [{version}]",),
    }
    for relative_path, markers in required_markers.items():
        if relative_path not in paths:
            errors.append(f"Missing version-bearing file: {relative_path}")
            continue
        content = read_repository_text(PurePosixPath(relative_path))
        for marker in markers:
            if marker not in content:
                errors.append(f"{relative_path} is missing canonical-version marker: {marker}")

    literal_pattern = re.compile(r"v\d+\.\d+\.\d+")
    for relative_path in ("main.py", "ui/main_window.py"):
        if relative_path not in paths:
            continue
        stray = sorted(
            set(literal_pattern.findall(read_repository_text(PurePosixPath(relative_path))))
        )
        if stray:
            errors.append(
                f"{relative_path} hard-codes a literal application version: {', '.join(stray)}"
            )

    package_workflow = PurePosixPath(".github/workflows/package.yml")
    if package_workflow.as_posix() in paths:
        workflow_text = read_repository_text(package_workflow)
        for expected in re.findall(r"--expected-version\s+(\S+)", workflow_text):
            if expected != version:
                errors.append(
                    f"package.yml --expected-version {expected} diverges from "
                    f"canonical version {version}"
                )

    if project.get("license") != "MIT":
        errors.append("pyproject.toml must use the SPDX license expression MIT")
    if project.get("license-files") != ["LICENSE"]:
        errors.append("pyproject.toml must explicitly include LICENSE")
    return errors


def github_heading_slugs(markdown: str) -> set[str]:
    slugs: set[str] = set()
    duplicate_counts: dict[str, int] = {}
    for line in markdown.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", match.group(1))
        heading = re.sub(r"<[^>]+>", "", heading).replace("`", "").lower()
        base_slug = re.sub(r"[^\w\- ]", "", heading)
        base_slug = re.sub(r"\s+", "-", base_slug).strip("-")
        occurrence = duplicate_counts.get(base_slug, 0)
        duplicate_counts[base_slug] = occurrence + 1
        slugs.add(base_slug if occurrence == 0 else f"{base_slug}-{occurrence}")
    return slugs


def split_markdown_target(raw_target: str) -> tuple[str, str]:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    path_part, separator, fragment = target.partition("#")
    return unquote(path_part), unquote(fragment) if separator else ""


def verify_markdown_links(paths: list[PurePosixPath]) -> list[str]:
    errors: list[str] = []
    markdown_paths = [path for path in paths if path.suffix.lower() == ".md"]
    for source_path in markdown_paths:
        source_file = REPOSITORY_ROOT.joinpath(*source_path.parts)
        content = read_repository_text(source_path)
        for raw_target in MARKDOWN_LINK_PATTERN.findall(content):
            path_part, fragment = split_markdown_target(raw_target)
            if re.match(r"^[a-z][a-z0-9+.-]*:", path_part, re.IGNORECASE) or path_part.startswith(
                "//"
            ):
                continue
            target_file = (
                source_file if not path_part else (source_file.parent / path_part).resolve()
            )
            try:
                target_file.relative_to(REPOSITORY_ROOT)
            except ValueError:
                errors.append(f"{source_path}: link escapes repository: {raw_target}")
                continue
            if not target_file.exists():
                errors.append(f"{source_path}: missing link target: {raw_target}")
                continue
            if fragment and target_file.suffix.lower() == ".md":
                target_content = target_file.read_text(encoding="utf-8-sig")
                if fragment.lower() not in github_heading_slugs(target_content):
                    errors.append(f"{source_path}: missing Markdown anchor: {raw_target}")
    return errors


def is_temporary_path(path: PurePosixPath) -> bool:
    for part in path.parts:
        lowered = part.lower()
        if lowered.endswith((".tmp", ".temp", ".swp", ".swo", "~")) or lowered.startswith(".#"):
            return True
    return False


def verify_tracked_content(paths: list[PurePosixPath]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        normalized = path.as_posix().lower()
        lowered_parts = {part.lower() for part in path.parts}
        name = path.name.lower()
        if normalized in LEGACY_DOCUMENTATION_PATHS:
            errors.append(f"Forbidden legacy documentation is present: {path}")
        if lowered_parts & FORBIDDEN_TRACKED_COMPONENTS:
            errors.append(f"Generated/build path must not be tracked: {path}")
        if name == ".coverage" or name.startswith(".coverage.") or name == "coverage.xml":
            errors.append(f"Coverage output must not be tracked: {path}")
        if is_temporary_path(path):
            errors.append(f"Temporary file must not be tracked: {path}")
        if "transcript" in name or re.search(r"status[-_. ]?dump", name):
            errors.append(f"Generated agent/status output must not be tracked: {path}")
        if path.suffix.lower() in {".html", ".csv"} or re.match(r"report.*\.json$", name):
            errors.append(f"Generated report output must not be tracked: {path}")
    return errors


def verify_documentation_governance(paths: set[str]) -> list[str]:
    errors = [
        f"Missing canonical documentation: {path}"
        for path in sorted(REQUIRED_DOCUMENTATION_PATHS - paths)
    ]
    if "AGENTS.md" not in paths:
        return errors
    agents = read_repository_text(PurePosixPath("AGENTS.md"))
    for rule_number in range(1, 8):
        rule_id = f"DOC-0{rule_number}"
        if rule_id not in agents:
            errors.append(f"AGENTS.md is missing governance rule {rule_id}")
    return errors


def verify_workflows(paths: set[str]) -> list[str]:
    errors: list[str] = []
    workflow_paths = sorted(
        path
        for path in paths
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    )
    expected_workflows = {
        ".github/workflows/ci.yml",
        ".github/workflows/package.yml",
        ".github/workflows/dependency-review.yml",
    }
    for missing in sorted(expected_workflows - set(workflow_paths)):
        errors.append(f"Missing required workflow: {missing}")

    all_job_names: list[str] = []
    for workflow_path in workflow_paths:
        content = read_repository_text(PurePosixPath(workflow_path))
        if "pull_request_target" in content:
            errors.append(f"{workflow_path} must not use pull_request_target")
        if not re.search(r"^permissions:\s*\n  contents: read\s*$", content, re.MULTILINE):
            errors.append(f"{workflow_path} must declare top-level contents: read permission")
        if "concurrency:" not in content or "cancel-in-progress: true" not in content:
            errors.append(f"{workflow_path} must cancel superseded concurrent runs")
        if content.count("timeout-minutes:") != content.count("runs-on:"):
            errors.append(f"{workflow_path} must define a timeout for every job")
        for action_reference in ACTION_REFERENCE_PATTERN.findall(content):
            if action_reference.startswith("./"):
                continue
            if not FULL_SHA_ACTION_PATTERN.fullmatch(action_reference):
                errors.append(f"{workflow_path} has an unpinned action: {action_reference}")
        _, jobs_marker, jobs_section = content.partition("\njobs:\n")
        if not jobs_marker:
            errors.append(f"{workflow_path} is missing a jobs section")
            continue
        all_job_names.extend(JOB_IDENTIFIER_PATTERN.findall(jobs_section))

    duplicates = sorted({name for name in all_job_names if all_job_names.count(name) > 1})
    if duplicates:
        errors.append(f"Duplicate workflow job identifiers: {', '.join(duplicates)}")
    missing_checks = sorted(REQUIRED_CHECK_NAMES - set(all_job_names))
    if missing_checks:
        errors.append(f"Missing stable workflow jobs: {', '.join(missing_checks)}")
    return errors


def verify_changed_line_hygiene() -> list[str]:
    dirty = bool(run_git("status", "--porcelain").stdout.strip())
    commands = [("diff", "--check"), ("diff", "--cached", "--check")]
    if not dirty:
        parent = run_git("rev-parse", "HEAD^", check=False)
        if parent.returncode == 0:
            commands = [("diff", "--check", parent.stdout.strip(), "HEAD")]

    errors: list[str] = []
    for command in commands:
        result = run_git(*command, check=False)
        if result.returncode != 0:
            detail = (result.stdout + result.stderr).strip()
            errors.append(f"git {' '.join(command)} failed: {detail}")
    return errors


def main() -> int:
    paths = repository_paths()
    path_strings = {path.as_posix() for path in paths}
    errors = [
        *verify_tracked_content(paths),
        *verify_version_truth(path_strings),
        *verify_markdown_links(paths),
        *verify_documentation_governance(path_strings),
        *verify_workflows(path_strings),
        *verify_changed_line_hygiene(),
    ]
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise RepositoryVerificationError(
            f"Repository verification failed with {len(errors)} error(s)"
        )

    print(f"Repository truth verified across {len(paths)} versioned/candidate paths.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RepositoryVerificationError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
