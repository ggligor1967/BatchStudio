#!/usr/bin/env python3
"""Validate built distributions and an isolated wheel installation."""

from __future__ import annotations

import argparse
import email.policy
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


FORBIDDEN_ARCHIVE_COMPONENTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
}


class PackageVerificationError(RuntimeError):
    """Raised when a distribution or isolated installation is invalid."""


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args()


def is_temporary_member(path: PurePosixPath) -> bool:
    return any(
        part.lower().endswith((".tmp", ".temp", ".swp", ".swo", "~"))
        or part.lower().startswith(".#")
        for part in path.parts
    )


def verify_archive_members(archive_name: str, member_names: list[str]) -> None:
    errors: list[str] = []
    for member_name in member_names:
        path = PurePosixPath(member_name.replace("\\", "/"))
        lowered_parts = {part.lower() for part in path.parts}
        if lowered_parts & FORBIDDEN_ARCHIVE_COMPONENTS:
            errors.append(member_name)
        elif ".coverage" in lowered_parts or is_temporary_member(path):
            errors.append(member_name)
    if errors:
        raise PackageVerificationError(
            f"{archive_name} contains forbidden members: {', '.join(sorted(errors))}"
        )


def metadata_from_wheel(wheel: Path) -> email.message.EmailMessage:
    with zipfile.ZipFile(wheel) as archive:
        members = archive.namelist()
        verify_archive_members(wheel.name, members)
        metadata_members = [name for name in members if name.endswith(".dist-info/METADATA")]
        if len(metadata_members) != 1:
            raise PackageVerificationError(f"{wheel.name} must contain exactly one METADATA file")
        return BytesParser(policy=email.policy.default).parsebytes(
            archive.read(metadata_members[0])
        )


def metadata_from_sdist(sdist: Path) -> email.message.EmailMessage:
    with tarfile.open(sdist, mode="r:gz") as archive:
        members = archive.getnames()
        verify_archive_members(sdist.name, members)
        metadata_members = [
            name for name in members if name.count("/") == 1 and name.endswith("/PKG-INFO")
        ]
        if len(metadata_members) != 1:
            raise PackageVerificationError(
                f"{sdist.name} must contain exactly one top-level PKG-INFO file"
            )
        extracted = archive.extractfile(metadata_members[0])
        if extracted is None:
            raise PackageVerificationError(
                f"Could not read {metadata_members[0]} from {sdist.name}"
            )
        return BytesParser(policy=email.policy.default).parsebytes(extracted.read())


def verify_distribution_metadata(
    metadata: email.message.EmailMessage, expected_version: str, source: str
) -> None:
    if metadata.get("Name", "").lower() != "batchstudio":
        raise PackageVerificationError(
            f"{source} has unexpected project name: {metadata.get('Name')}"
        )
    if metadata.get("Version") != expected_version:
        raise PackageVerificationError(
            f"{source} has unexpected version: {metadata.get('Version')}"
        )
    if metadata.get("License-Expression") != "MIT":
        raise PackageVerificationError(f"{source} is missing the MIT SPDX license expression")
    if not any(value.endswith("LICENSE") for value in metadata.get_all("License-File", [])):
        raise PackageVerificationError(f"{source} is missing LICENSE metadata")


def virtual_environment_python(environment_directory: Path) -> Path:
    if sys.platform == "win32":
        return environment_directory / "Scripts" / "python.exe"
    return environment_directory / "bin" / "python"


def verify_isolated_wheel_install(wheel: Path, expected_version: str) -> None:
    probe = f"""
from importlib import import_module, metadata

distribution = metadata.distribution("batchstudio")
assert distribution.version == {expected_version!r}, distribution.version
for module_name in ("core", "core.processor", "core.workflow", "core.operations", "ui", "main"):
    import_module(module_name)
entry_points = [
    entry
    for entry in distribution.entry_points
    if entry.group == "gui_scripts" and entry.name == "batchstudio-gui"
]
assert len(entry_points) == 1, entry_points
loaded_entrypoint = entry_points[0].load()
assert callable(loaded_entrypoint), loaded_entrypoint
print("Installed package imports and batchstudio-gui entrypoint verified.")
"""
    with tempfile.TemporaryDirectory(prefix="batchstudio-wheel-") as temporary_directory:
        temporary_root = Path(temporary_directory)
        environment_directory = temporary_root / "venv"
        probe_directory = temporary_root / "outside-repository"
        probe_directory.mkdir()
        venv.EnvBuilder(with_pip=True, clear=True).create(environment_directory)
        python = virtual_environment_python(environment_directory)
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(wheel.resolve()),
            ],
            cwd=probe_directory,
            check=True,
        )
        subprocess.run([str(python), "-m", "pip", "check"], cwd=probe_directory, check=True)
        subprocess.run([str(python), "-I", "-c", probe], cwd=probe_directory, check=True)


def main() -> int:
    arguments = parse_arguments()
    dist_directory = arguments.dist_dir.resolve()
    artifacts = sorted(path for path in dist_directory.iterdir() if path.is_file())
    wheels = [path for path in artifacts if path.suffix == ".whl"]
    sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
    if len(artifacts) != 2 or len(wheels) != 1 or len(sdists) != 1:
        artifact_names = ", ".join(path.name for path in artifacts) or "none"
        raise PackageVerificationError(
            f"Expected exactly one wheel and one sdist; found: {artifact_names}"
        )

    wheel_metadata = metadata_from_wheel(wheels[0])
    sdist_metadata = metadata_from_sdist(sdists[0])
    verify_distribution_metadata(wheel_metadata, arguments.expected_version, wheels[0].name)
    verify_distribution_metadata(sdist_metadata, arguments.expected_version, sdists[0].name)
    verify_isolated_wheel_install(wheels[0], arguments.expected_version)
    print(f"Verified wheel and sdist for BatchStudio {arguments.expected_version}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, PackageVerificationError, subprocess.CalledProcessError) as error:
        print(f"Package verification failed: {error}", file=sys.stderr)
        raise SystemExit(1) from None
