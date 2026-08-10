"""Validate the immutable pre-Issue-66 milestone registry as historical evidence."""

from __future__ import annotations

import sys
from pathlib import Path

from validate_milestones import load_registry, validate_git_history, validate_registry_data


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    registry = root / "docs" / "MILESTONE_STATE.json"
    data = load_registry(registry)
    errors = validate_registry_data(data)
    errors.extend(validate_git_history(data, root, registry))
    if errors:
        print("Legacy milestone-history validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        f"Validated {len(data['milestones'])} immutable legacy FXD milestone records; "
        "current work selection is owned by docs/CONTROL_STATE.json and CURRENT.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
