#!/usr/bin/env python3
"""Create a deterministic hash manifest for explicit reviewed release artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


SENSITIVE_PARTS = {".git", ".fxd", ".venv", "venv", "__pycache__", "customer", "customers"}


def _collect_artifacts(root: Path, output: Path, arguments: list[str]) -> tuple[Path, ...]:
    if not arguments:
        raise ValueError("at least one explicit release artifact is required")
    output_resolved = output.resolve(strict=False)
    files: set[Path] = set()
    for argument in arguments:
        candidate = (root / argument).resolve(strict=True)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"release artifact must remain inside the repository: {argument}") from exc
        relative_parts = set(candidate.relative_to(root).parts)
        if relative_parts & SENSITIVE_PARTS:
            raise ValueError(f"sensitive or local-only path cannot enter a release manifest: {argument}")
        candidates = (candidate,) if candidate.is_file() else tuple(candidate.rglob("*"))
        for path in candidates:
            if not path.is_file() or path.is_symlink() or path.resolve() == output_resolved:
                continue
            relative = path.relative_to(root)
            if set(relative.parts) & SENSITIVE_PARTS:
                raise ValueError(f"sensitive or local-only path cannot enter a release manifest: {relative}")
            files.add(path)
    if not files:
        raise ValueError("no regular release artifacts were selected")
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def build_manifest(version: str, output: Path, artifacts: list[str], *, root: Path) -> dict[str, object]:
    version = version.strip()
    if not version or any(character.isspace() for character in version):
        raise ValueError("release version must be a non-empty token")
    files = _collect_artifacts(root, output, artifacts)
    return {
        "format": "fxd-release-manifest-v1",
        "version": version,
        "engineering_review_required": True,
        "production_approval": False,
        "files": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files
        },
    }


def write_manifest(manifest: dict[str, object], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return output


def main() -> None:
    if len(sys.argv) < 4:
        raise SystemExit("usage: release-manifest.py VERSION OUTPUT ARTIFACT [ARTIFACT ...]")
    root = Path(__file__).resolve().parents[1]
    version, output = sys.argv[1], Path(sys.argv[2])
    if not output.is_absolute():
        output = root / output
    try:
        manifest = build_manifest(version, output, sys.argv[3:], root=root)
        write_manifest(manifest, output)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
