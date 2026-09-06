"""V11-R release-candidate guards.

These tests assert one canonical application version source shared by packaging
metadata, the runtime banner, and the desktop UI displays, plus a small set of
release-documentation invariants. They do not exercise OCR behavior and do not
add behavioral Tkinter coverage.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL = "1.1.0"


def _read_text(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8-sig")


def _load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_canonical_version_module_is_plain_semver():
    from core import _version

    assert _version.__version__ == CANONICAL
    assert re.fullmatch(r"\d+\.\d+\.\d+", _version.__version__)


def test_core_package_reexports_canonical_version():
    import core
    from core import _version

    assert core.__version__ is _version.__version__


def test_pyproject_declares_dynamic_version_from_canonical_module():
    # Parser-free: stdlib tomllib is 3.11+, and CI exercises this on Python 3.10 too.
    text = _read_text("pyproject.toml")
    assert re.search(r'(?m)^dynamic\s*=\s*\["version"\]\s*$', text)
    assert not re.search(r'(?m)^version\s*=\s*"', text), "pyproject must not pin a literal version"
    assert 'version = {attr = "core._version.__version__"}' in text


def test_runtime_banner_module_uses_canonical_version():
    main = importlib.import_module("main")
    assert main.__version__ == CANONICAL
    source = _read_text("main.py")
    assert "BATCHSTUDIO v{__version__}" in source
    assert not re.search(r"v\d+\.\d+\.\d+", source)


def test_ui_version_surfaces_use_canonical_version():
    source = _read_text("ui/main_window.py")
    assert "from core import __version__" in source
    assert 'f"v{__version__}"' in source
    assert "BatchStudio v{__version__}" in source
    assert not re.search(r"v\d+\.\d+\.\d+", source)


def test_installed_distribution_metadata_matches_canonical():
    try:
        installed = importlib.metadata.version("batchstudio")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("batchstudio distribution is not installed in this environment")
    assert installed == CANONICAL


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="scripts/verify_repository.py requires stdlib tomllib (Python 3.11+)",
)
def test_repository_verifier_version_contract_passes():
    verifier = _load_script("v11r_verify_repository", "scripts/verify_repository.py")
    paths = {path.as_posix() for path in verifier.repository_paths()}
    assert verifier.verify_version_truth(paths) == []


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="scripts/verify_repository.py requires stdlib tomllib (Python 3.11+)",
)
def test_repository_verifier_flags_a_diverging_package_workflow(monkeypatch):
    verifier = _load_script("v11r_verify_repository_div", "scripts/verify_repository.py")
    original = verifier.read_repository_text

    def patched(path):
        text = original(path)
        if path.as_posix() == ".github/workflows/package.yml":
            return text.replace("--expected-version 1.1.0", "--expected-version 9.9.9")
        return text

    monkeypatch.setattr(verifier, "read_repository_text", patched)
    paths = {path.as_posix() for path in verifier.repository_paths()}
    errors = verifier.verify_version_truth(paths)
    assert any("diverges from" in error for error in errors)


def test_package_verifier_rejects_expected_version_divergence():
    verifier = _load_script("v11r_verify_package", "scripts/verify_package.py")
    assert verifier.read_canonical_version() == CANONICAL


def test_package_workflow_expected_version_matches_canonical():
    workflow = _read_text(".github/workflows/package.yml")
    assert re.findall(r"--expected-version\s+(\S+)", workflow) == [CANONICAL]


def test_changelog_has_candidate_section():
    assert f"## [{CANONICAL}]" in _read_text("CHANGELOG.md")


def test_release_process_routes_through_protected_pull_request():
    lowered = _read_text("docs/RELEASE_PROCESS.md").lower()
    # The old instruction to push main directly must be gone...
    assert "push `main` without force" not in lowered
    # ...replaced by an explicit prohibition and the protected PR integration path.
    assert "never push `main` directly" in lowered
    assert "git push origin main" in lowered
    assert "pull request" in lowered
    assert "protected" in lowered


def test_ocr_docs_distinguish_mocked_and_controlled_real_qualification():
    for doc in ("docs/OCR.md", "docs/LIMITATIONS.md", "docs/OPERATIONS.md", "docs/TESTING.md"):
        lowered = _read_text(doc).lower()
        assert "qualification remains outstanding" not in lowered, doc
        assert "real ocr success remains unverified" not in lowered, doc
        assert "real ocr success is not verified" not in lowered, doc
    ocr = _read_text("docs/OCR.md")
    assert "deferred" in ocr.lower()
    assert "fail-closed real-ocr qualification" in ocr.lower()
    assert "exact commit" in ocr.lower()
    assert "not certification" in ocr.lower()
    assert "#10" in ocr


def test_roadmap_marks_v12_03_complete_and_v12_04_next():
    text = _read_text("docs/ROADMAP.md")
    lowered = text.lower()
    assert "v11-08" in lowered
    assert "v11-08 behavioral tkinter coverage" in lowered
    assert "v12-01 final-name collision protection" in lowered
    assert "#25" in text
    assert "v12-02 aggregate semantic hardening" in lowered
    assert "#27" in text
    assert "v11-06 controlled real-ocr qualification" in lowered
    assert "v12-03 format-capability decision" in lowered
    assert "#33" in text
    assert "**v12-04 is the next admissible implementation unit**" in lowered
    assert "### v12-03" not in lowered
    assert "- **v12-01" not in lowered
    assert "### v12-02" not in lowered
    assert "- **v11-08" not in lowered
    assert "## active deferred v1.1 unit" not in lowered
    assert "v11-06" in lowered
    assert "#10" in text

    changelog = _read_text("CHANGELOG.md")
    assert "At the 1.1.0 release boundary" in changelog
    assert "[Roadmap](docs/ROADMAP.md) marks" not in changelog
