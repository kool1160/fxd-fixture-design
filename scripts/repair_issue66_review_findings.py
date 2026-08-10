"""One-time deterministic repair for the two blocking PR #67 review findings.

The selector itself is repaired separately. This script pins current-control validation to the
required historical-registry path and updates legacy selector tests to prove retirement remains
fail-closed even when the operator protocol is absent.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_control_state.py"
TESTS = ROOT / "tests" / "test_milestone_governance.py"
MARKER = "# ISSUE66_REVIEW_REPAIR_COMPLETE"

OLD_VALIDATOR = '''    legacy_path = repo_root / str(legacy.get("path", ""))
    if legacy.get("authority") != "historical_only":
        errors.append("legacy milestone registry must be classified historical_only")
'''
NEW_VALIDATOR = '''    expected_legacy_path = "docs/MILESTONE_STATE.json"
    if legacy.get("path") != expected_legacy_path:
        errors.append(
            "legacy milestone registry path must remain "
            f"{expected_legacy_path!r}, got {legacy.get('path')!r}"
        )
    legacy_path = repo_root / expected_legacy_path
    if legacy.get("authority") != "historical_only":
        errors.append("legacy milestone registry must be classified historical_only")
'''

REPLACEMENTS = {
    "test_registry_selector_returns_governed_no_selection_for_paused_lane": '''    def test_registry_selector_returns_governed_no_selection_for_paused_lane(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.data()
            self.milestone(data, 32)["status"] = "Planned"
            data["product_lane"].update(
                {
                    "paused": True,
                    "active_milestone": None,
                    "pause_reason": "Approved selector pause.",
                    "decision": "Issue #999 approved the selector pause.",
                }
            )
            self.build_selector_repository(root, data)
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", selected.stderr)
        self.assertNotIn("Selected", selected.stdout)
''',
    "test_registry_selector_does_not_consult_backlog": '''    def test_registry_selector_does_not_consult_backlog(self) -> None:
        # Even an isolated checkout with no OPERATOR_PROTOCOL.md and no BACKLOG.md
        # cannot re-enable the superseded selector.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_selector_repository(root)
            self.assertFalse((root / "BACKLOG.md").exists())
            self.assertFalse((root / "docs" / "OPERATOR_PROTOCOL.md").exists())
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", selected.stderr)
        self.assertNotIn("Selected", selected.stdout)
''',
}


def repair_validator() -> None:
    source = VALIDATOR.read_text(encoding="utf-8")
    if NEW_VALIDATOR in source:
        return
    if OLD_VALIDATOR not in source:
        raise RuntimeError("expected legacy-path validator block was not found")
    VALIDATOR.write_text(source.replace(OLD_VALIDATOR, NEW_VALIDATOR, 1), encoding="utf-8")


def repair_tests() -> None:
    source = TESTS.read_text(encoding="utf-8")
    if MARKER in source:
        return
    tree = ast.parse(source)
    test_class = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MilestoneGovernanceTests"
        ),
        None,
    )
    if test_class is None:
        raise RuntimeError("MilestoneGovernanceTests class was not found")
    methods = {
        node.name: node
        for node in test_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(set(REPLACEMENTS) - set(methods))
    if missing:
        raise RuntimeError(f"expected selector test methods are missing: {missing}")

    lines = source.splitlines(keepends=True)
    edits: list[tuple[int, int, str]] = []
    for name, replacement in REPLACEMENTS.items():
        node = methods[name]
        if node.end_lineno is None:
            raise RuntimeError(f"AST has no end line for {name}")
        edits.append((node.lineno - 1, node.end_lineno, replacement + "\n"))
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = [replacement]

    migrated = MARKER + "\n" + "".join(lines)
    ast.parse(migrated)
    TESTS.write_text(migrated, encoding="utf-8")


def main() -> None:
    repair_validator()
    repair_tests()
    print("Applied both Issue #66 review repairs.")


if __name__ == "__main__":
    main()
