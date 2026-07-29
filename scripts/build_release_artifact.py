#!/usr/bin/env python3
"""Build a deterministic, checksummed Practenture source release artifact."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

EXCLUDED_DIRS = {
    ".git",
    ".hermes",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
    # Generated Xcode/SwiftPM material and local user state are not source.
    "build",
    ".build",
    "DerivedData",
    "SourcePackages",
    "xcuserdata",
}
# Linked Git worktrees represent .git as a file rather than a directory.
EXCLUDED_NAMES = {".env", ".ec2-state.json", ".DS_Store", ".git"}
EXCLUDED_SUFFIXES = {".db", ".db-shm", ".db-wal", ".pyc", ".sqlite", ".sqlite3"}
MANIFEST_NAME = "RELEASE-MANIFEST.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect(root: Path, output: Path) -> list[tuple[str, bytes, int]]:
    files: list[tuple[str, bytes, int]] = []
    output_paths = {output.resolve(), Path(f"{output}.sha256").resolve()}
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        base = Path(directory)
        for name in sorted(filenames):
            source = base / name
            if source.resolve() in output_paths or name in EXCLUDED_NAMES:
                continue
            if any(name.endswith(suffix) for suffix in EXCLUDED_SUFFIXES):
                continue
            if source.is_symlink() or not source.is_file():
                continue
            relative = source.relative_to(root).as_posix()
            data = source.read_bytes()
            mode = 0o755 if source.stat().st_mode & 0o111 else 0o644
            files.append((relative, data, mode))
    return sorted(files, key=lambda item: item[0])


def tar_entry(name: str, data: bytes, mode: int) -> tuple[tarfile.TarInfo, io.BytesIO]:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    info.mode = mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    return info, io.BytesIO(data)


def build(root: Path, output: Path) -> str:
    root = root.resolve()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = collect(root, output)
    manifest = {
        "formatVersion": 1,
        "files": [
            {"path": path, "sha256": sha256(data), "size": len(data)}
            for path, data, _mode in files
        ],
    }
    manifest_data = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()

    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path, data, mode in files:
                    info, stream = tar_entry(path, data, mode)
                    archive.addfile(info, stream)
                info, stream = tar_entry(MANIFEST_NAME, manifest_data, 0o644)
                archive.addfile(info, stream)

    digest = sha256(output.read_bytes())
    checksum = Path(f"{output}.sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    digest = build(args.root, args.output)
    print(f"artifact={args.output}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
