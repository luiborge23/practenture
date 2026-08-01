#!/usr/bin/env python3
"""Verify an extracted Practenture release against its immutable manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

MANIFEST_NAME = "RELEASE-MANIFEST.json"
RUNTIME_FILES = {
    ".activation-complete",
    ".activation-started",
    ".deploy-id",
    ".env",
    ".promotion-complete",
    ".release-artifact-sha256",
    ".rollback-image",
    ".source-revision",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path, expected_revision: str, expected_manifest_sha256: str) -> None:
    root = root.resolve(strict=True)
    manifest_path = root / MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("release manifest is missing or unsafe")
    if sha256(manifest_path) != expected_manifest_sha256:
        raise ValueError("release manifest digest does not match the uploaded artifact")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("formatVersion") != 1:
        raise ValueError("unsupported release manifest format")
    if manifest.get("sourceRevision") != expected_revision:
        raise ValueError("release manifest source revision does not match")

    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = entry.get("path")
        if not isinstance(relative, str):
            raise ValueError("release manifest contains a non-string path")
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or str(pure) != relative:
            raise ValueError(f"unsafe release manifest path: {relative}")
        if relative in expected:
            raise ValueError(f"duplicate release manifest path: {relative}")
        expected.add(relative)
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing or unsafe release file: {relative}")
        if path.stat().st_size != entry.get("size"):
            raise ValueError(f"release file size mismatch: {relative}")
        if sha256(path) != entry.get("sha256"):
            raise ValueError(f"release file digest mismatch: {relative}")

    paths = list(root.rglob("*"))
    unsafe_link = next((path for path in paths if path.is_symlink()), None)
    if unsafe_link is not None:
        raise ValueError(
            f"release contains a symbolic link: {unsafe_link.relative_to(root)}"
        )
    actual = {
        path.relative_to(root).as_posix() for path in paths if path.is_file()
    }
    allowed = expected | RUNTIME_FILES | {MANIFEST_NAME}
    unexpected = sorted(actual - allowed)
    if unexpected:
        raise ValueError(f"unexpected release file: {unexpected[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("release", type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    verify(args.release, args.source_revision, args.manifest_sha256)
    print("RELEASE_MANIFEST_VERIFIED")


if __name__ == "__main__":
    main()
