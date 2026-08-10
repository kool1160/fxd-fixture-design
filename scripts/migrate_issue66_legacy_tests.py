"""One-time deterministic migration of pre-reset Foreman/selector tests.

The historical milestone registry tests remain. Only tests that asserted the now-rejected
runtime selector and autonomous Foreman behavior are rewritten to assert the accepted Issue #66
fail-closed control model. The transformation is AST-bounded and refuses unexpected source.
"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tests" / "test_milestone_governance.py"
MARKER = "# ISSUE66_TEST_MIGRATION_COMPLETE"


REPLACEMENTS = {
    "test_registry_selector_selects_only_active_m32": '''    def test_registry_selector_selects_only_active_m32(self) -> None:
        # The frozen registry still validates M32 history, but the real repository
        # selector must not turn that historical projection into executable work.
        with tempfile.TemporaryDirectory() as temp:
            context = Path(temp) / "selection.md"
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select", "--context", str(context)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertFalse(context.exists())
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", selected.stderr)
''',
    "test_registry_selector_does_not_consult_backlog": '''    def test_registry_selector_does_not_consult_backlog(self) -> None:
        # Isolated historical-registry fixtures retain compatibility coverage and
        # contain no current Review-Control protocol.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.build_selector_repository(root)
            self.assertFalse((root / "BACKLOG.md").exists())
            selected = subprocess.run(
                ["node", "scripts/fxd-backlog.mjs", "select"],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(0, selected.returncode, selected.stderr)
        self.assertIn("Selected compatibility Milestone 32", selected.stdout)
''',
    "test_registry_selector_cannot_silently_choose_m20": '''    def test_registry_selector_cannot_silently_choose_m20(self) -> None:
        selected = subprocess.run(
            ["node", "scripts/fxd-backlog.mjs", "select", "--number", "20"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(0, selected.returncode)
        self.assertIn("automatic milestone selection is retired by Issue #66", selected.stderr)
''',
    "test_foreman_validates_governance_before_selection": '''    def test_foreman_validates_governance_before_selection(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        self.assertIn("RETIRED BY ISSUE #66", workflow)
        self.assertIn("Use docs/OPERATOR_PROTOCOL.md", workflow)
        self.assertNotIn("name: Select milestone", workflow)
''',
    "test_foreman_rejects_closed_authoritative_milestone_issue": '''    def test_foreman_rejects_closed_authoritative_milestone_issue(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        self.assertIn("contents: read", workflow)
        self.assertNotIn("gh issue view", workflow)
        self.assertNotIn("issues: write", workflow)
''',
    "test_foreman_rejects_whitespace_only_authoritative_issue_body": '''    def test_foreman_rejects_whitespace_only_authoritative_issue_body(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        self.assertNotIn("selected-milestone.md", workflow)
        self.assertNotIn("issue_body", workflow)
        self.assertIn("exit 1", workflow)
''',
    "test_foreman_loads_open_issue_before_codex_execution": '''    def test_foreman_loads_open_issue_before_codex_execution(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        self.assertNotIn("openai/codex-action", workflow)
        self.assertNotIn("Run Codex milestone Foreman", workflow)
        self.assertIn("Refuse retired autonomous Foreman dispatch", workflow)
''',
    "test_foreman_issue_number_matches_registry_selection": '''    def test_foreman_issue_number_matches_registry_selection(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        self.assertNotIn("steps.milestone.outputs.issue_number", workflow)
        self.assertNotIn("gh issue view 57", workflow)
        self.assertIn("Issue #66 retired this autonomous workflow", workflow)
''',
    "test_foreman_rejects_authoritative_issue_repository_mismatch": '''    def test_foreman_rejects_authoritative_issue_repository_mismatch(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "fxd-foreman.yml").read_text(encoding="utf-8")
        self.assertNotIn("gh issue view", workflow)
        self.assertNotIn("GITHUB_REPOSITORY", workflow)
        self.assertNotIn("contents: write", workflow)
''',
}


def migrate() -> bool:
    source = TARGET.read_text(encoding="utf-8")
    if MARKER in source:
        print("Issue #66 legacy-test migration already applied.")
        return False

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
        raise RuntimeError(f"expected legacy test methods are missing: {missing}")

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
    TARGET.write_text(migrated, encoding="utf-8")
    print(f"Migrated {len(REPLACEMENTS)} obsolete Foreman/selector tests for Issue #66.")
    return True


if __name__ == "__main__":
    migrate()
