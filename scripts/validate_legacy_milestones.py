"""Validate a pre-Issue-66 milestone registry as historical evidence only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from validate_milestones import load_registry, validate_git_history, validate_registry_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an FXD milestone registry without granting it current-work authority."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("docs/MILESTONE_STATE.json"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    registry = args.registry
    if not registry.is_absolute():
        registry = root / registry
    registry = registry.resolve()

    try:
        registry.relative_to(root)
    except ValueError:
        print("Legacy milestone-history validation failed:", file=sys.stderr)
        print("- registry must remain inside the selected repository root", file=sys.stderr)
        return 1

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
