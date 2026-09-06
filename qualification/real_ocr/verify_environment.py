#!/usr/bin/env python3
"""Fail-closed verification for the controlled real-OCR environment."""

from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version as installed_version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any


class QualificationError(RuntimeError):
    """Raised when the controlled qualification contract is not satisfied."""


def sha256(path: Path) -> str:
    if not path.is_file():
        raise QualificationError(f"Required file is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_equal(label: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise QualificationError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def read_os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
        key, separator, raw_value = line.partition("=")
        if separator:
            values[key] = raw_value.strip().strip('"')
    return values


def run_checked(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=15,
    )
    if completed.returncode != 0:
        raise QualificationError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout}"
        )
    return completed.stdout.strip()


def verify_artifacts(contract: dict[str, Any], artifact_directory: Path) -> dict[str, str]:
    identities: dict[str, str] = {}
    for component_name in ("tesseract", "poppler"):
        component = contract["tools"][component_name]
        artifact = artifact_directory / component["artifact_name"]
        actual_hash = sha256(artifact)
        require_equal(
            f"{component_name} artifact SHA256", actual_hash, component["artifact_sha256"]
        )
        identities[f"{component_name}_artifact_sha256"] = actual_hash
    return identities


def verify_fixture_hashes(contract: dict[str, Any], repository_root: Path) -> dict[str, str]:
    identities: dict[str, str] = {}
    for fixture_name, fixture in contract["fixtures"].items():
        actual_hash = sha256(repository_root / fixture["path"])
        require_equal(f"{fixture_name} fixture SHA256", actual_hash, fixture["sha256"])
        identities[f"fixture_{fixture_name}_sha256"] = actual_hash
    return identities


def verify_external_toolchain(contract: dict[str, Any], traineddata_prefix: Path) -> dict[str, str]:
    identities: dict[str, str] = {}
    for component_name in ("tesseract", "poppler"):
        component = contract["tools"][component_name]
        actual_package_version = run_checked(
            ["/usr/bin/dpkg-query", "-W", "-f=${Version}", component["dpkg_name"]]
        )
        require_equal(
            f"{component_name} package version",
            actual_package_version,
            component["package_version"],
        )
        identities[f"{component_name}_package_version"] = actual_package_version

    expected_commands = {
        "tesseract": contract["tools"]["tesseract"]["runtime_path"],
        **dict(
            zip(
                contract["tools"]["poppler"]["commands"],
                contract["tools"]["poppler"]["runtime_paths"],
                strict=True,
            )
        ),
    }
    for command, expected_path in expected_commands.items():
        discovered = shutil.which(command)
        if discovered is None:
            raise QualificationError(f"Controlled executable is missing from PATH: {command}")
        actual_path = str(Path(discovered).resolve())
        require_equal(f"{command} runtime path", actual_path, expected_path)
        identities[f"{command}_path"] = actual_path
        identities[f"{command}_sha256"] = sha256(Path(actual_path))

    tesseract_output = run_checked([expected_commands["tesseract"], "--version"])
    if not tesseract_output.splitlines()[0].startswith("tesseract 5.3.4"):
        raise QualificationError(f"Wrong Tesseract runtime version: {tesseract_output}")
    identities["tesseract_version_output"] = tesseract_output.splitlines()[0]

    for command in ("pdfinfo", "pdftoppm"):
        version_output = run_checked([expected_commands[command], "-v"])
        if "version 24.02.0" not in version_output.splitlines()[0]:
            raise QualificationError(
                f"Wrong Poppler runtime version for {command}: {version_output}"
            )
        identities[f"{command}_version_output"] = version_output.splitlines()[0]

    language_data = contract["tools"]["eng_traineddata"]
    traineddata_path = traineddata_prefix / language_data["artifact_name"]
    actual_traineddata_hash = sha256(traineddata_path)
    require_equal(
        "eng.traineddata SHA256",
        actual_traineddata_hash,
        language_data["artifact_sha256"],
    )
    identities["eng_traineddata_path"] = str(traineddata_path.resolve())
    identities["eng_traineddata_sha256"] = actual_traineddata_hash
    return identities


def verify_environment(
    repository_root: Path,
    contract_path: Path,
    artifact_directory: Path,
) -> dict[str, str]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    expected_environment = contract["environment"]

    require_equal("platform", platform.system().lower(), "linux")
    require_equal("architecture", platform.machine().lower(), expected_environment["architecture"])
    os_release = read_os_release()
    require_equal("OS ID", os_release.get("ID", ""), expected_environment["os_id"])
    require_equal(
        "OS version", os_release.get("VERSION_ID", ""), expected_environment["os_version"]
    )
    actual_python = platform.python_version()
    require_equal("Python version", actual_python, expected_environment["python"])

    identities = {
        "repository_sha": run_checked(["git", "-C", str(repository_root), "rev-parse", "HEAD"]),
        "os": f"{os_release['ID']} {os_release['VERSION_ID']}",
        "architecture": platform.machine().lower(),
        "python": actual_python,
    }
    expected_repository_sha = os.environ.get("QUALIFICATION_REPOSITORY_SHA") or os.environ.get(
        "GITHUB_SHA"
    )
    if expected_repository_sha:
        require_equal(
            "checked-out repository SHA",
            identities["repository_sha"],
            expected_repository_sha,
        )

    for package_name, expected_version in contract["python_packages"].items():
        actual_version = installed_version(package_name)
        require_equal(f"Python package {package_name}", actual_version, expected_version)
        identities[f"python_package_{package_name}"] = actual_version

    traineddata_prefix = os.environ.get("TESSDATA_PREFIX")
    if not traineddata_prefix:
        raise QualificationError("TESSDATA_PREFIX is not set")
    identities.update(verify_artifacts(contract, artifact_directory))
    identities.update(verify_external_toolchain(contract, Path(traineddata_prefix)))
    identities.update(verify_fixture_hashes(contract, repository_root))
    return identities


def main() -> int:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=default_root)
    parser.add_argument("--contract", type=Path, default=Path(__file__).with_name("contract.json"))
    parser.add_argument("--artifact-directory", type=Path, required=True)
    arguments = parser.parse_args()
    evidence = verify_environment(
        arguments.repository_root.resolve(),
        arguments.contract.resolve(),
        arguments.artifact_directory.resolve(),
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print("REAL_OCR_ENVIRONMENT_VERIFIED=YES")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"REAL_OCR_ENVIRONMENT_VERIFIED=NO: {error}", file=sys.stderr)
        raise SystemExit(1) from None
