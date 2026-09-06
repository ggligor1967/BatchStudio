#!/usr/bin/env python3
"""Download controlled OCR artifacts and reject every identity mismatch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with urlopen(url, timeout=60) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        actual_sha256 = sha256(partial)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"SHA256 mismatch for {destination.name}: "
                f"expected {expected_sha256}, got {actual_sha256}"
            )
        partial.replace(destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
        default=Path(__file__).with_name("contract.json"),
    )
    arguments = parser.parse_args()
    contract = json.loads(arguments.contract.read_text(encoding="utf-8"))

    for component_name in ("tesseract", "poppler"):
        component = contract["tools"][component_name]
        destination = arguments.destination / component["artifact_name"]
        download_verified(component["artifact_url"], destination, component["artifact_sha256"])
        print(f"VERIFIED {destination.name} sha256={component['artifact_sha256']}")

    language_data = contract["tools"]["eng_traineddata"]
    language_destination = arguments.destination / "tessdata" / language_data["artifact_name"]
    download_verified(
        language_data["artifact_url"],
        language_destination,
        language_data["artifact_sha256"],
    )
    print(f"VERIFIED {language_destination.name} " f"sha256={language_data['artifact_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
