#!/usr/bin/env python3
"""Create a deterministic hash manifest for a reviewed release candidate."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: release-manifest.py VERSION OUTPUT")
    version, output = sys.argv[1], Path(sys.argv[2])
    root = Path(__file__).parent.parent
    files = sorted(path for path in root.rglob("*") if path.is_file()
                   and ".git" not in path.parts and path != output)
    manifest = {"format": "fxd-release-manifest-v1", "version": version,
                "engineering_review_required": True,
                "files": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in files}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
