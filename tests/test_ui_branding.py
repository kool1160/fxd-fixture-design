import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from hashlib import sha256
from importlib.util import find_spec
from pathlib import Path
import unittest

if find_spec("PySide6") is None:
    raise unittest.SkipTest("PySide6 desktop runtime is not installed")

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from fxd_ui import ApprovalGatePanel, SourceCadBadge, StatusChip, WorkflowRail
from fxd_ui.theme import apply_fxd_theme, application_icon, asset_path, icon
from fxd_ui.theme.tokens import COLORS, DIMENSIONS, TECHNICAL_FONT, UI_FONT


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = (
    ROOT / "assets" / "branding" / "manifest" /
    "FXD_UI_Branding_Kit_v1.1_MANIFEST.json"
)


class BrandingAssetTests(unittest.TestCase):
    def test_approved_tokens_match_imported_v11_contract(self):
        data = json.loads((ROOT / "fxd_ui" / "theme" / "fxd.tokens.json").read_text())
        self.assertEqual(data["meta"]["version"], "1.1.0")
        expected = {
            "carbon": COLORS.carbon, "graphite": COLORS.graphite,
            "panel": COLORS.panel, "raised": COLORS.raised,
            "border": COLORS.border, "steel": COLORS.steel,
            "muted": COLORS.muted, "blue": COLORS.blue,
            "orange": COLORS.orange, "pass": COLORS.passed,
            "warning": COLORS.warning, "fail": COLORS.fail,
            "notEvaluated": COLORS.not_evaluated, "override": COLORS.override,
        }
        for key, value in expected.items():
            self.assertEqual(data["color"][key], value)
        self.assertEqual(data["font"]["ui"], UI_FONT)
        self.assertEqual(data["font"]["technical"], TECHNICAL_FONT)
        self.assertEqual(data["size"]["workflowRail"], DIMENSIONS.workflow_rail)

    def test_every_imported_production_asset_matches_kit_manifest(self):
        manifest = json.loads(SOURCE_MANIFEST.read_text())
        hashes = {item["path"]: item["sha256"] for item in manifest["files"]}
        mappings = []
        for file in (ROOT / "assets" / "icons" / "toolbar").iterdir():
            mappings.append((file, f"assets/icons/qt/{file.name}"))
        for file in (ROOT / "assets" / "branding" / "app-icons").iterdir():
            mappings.append((file, f"assets/app-icons/{file.name}"))
        logo_sources = {
            "fxd-icon-flat-color.svg": "assets/logos/vector/fxd-icon-flat-color.svg",
            "fxd-logo-flat-color.svg": "assets/logos/vector/fxd-logo-flat-color.svg",
            "fxd-logo-mono-white.svg": "assets/logos/vector/fxd-logo-mono-white.svg",
            "fxd-logo-approved-dark-1600x900.png":
                "assets/logos/raster/fxd-logo-approved-dark-1600x900.png",
        }
        for name, source in logo_sources.items():
            mappings.append((ROOT / "assets" / "branding" / "logos" / name, source))
        mappings.extend((
            (ROOT / "fxd_ui" / "theme" / "fxd.base.qss", "design-system/tokens/fxd.qss"),
            (ROOT / "fxd_ui" / "theme" / "fxd.tokens.json",
             "design-system/tokens/fxd.tokens.json"),
            (ROOT / "docs" / "ui-branding" / "BRAND_GUIDE.md", "brand/FXD_BRAND_GUIDE.md"),
            (ROOT / "docs" / "ui-branding" / "DESKTOP_APPLICATION_SHELL.md",
             "desktop/DESKTOP_APPLICATION_SHELL.md"),
            (ROOT / "docs" / "ui-branding" / "SOURCE_CAD_PROTECTION.md",
             "desktop/SOURCE_CAD_PROTECTION.md"),
            (ROOT / "docs" / "ui-branding" / "QT_THEME_SPECIFICATION.md",
             "qt/QT_THEME_SPECIFICATION.md"),
            (ROOT / "docs" / "ui-branding" / "ACCESSIBILITY_CHECKLIST.md",
             "implementation/ACCESSIBILITY_CHECKLIST.md"),
        ))
        self.assertEqual(len(mappings), 68)
        for file, source in mappings:
            with self.subTest(source=source):
                self.assertTrue(file.is_file())
                self.assertEqual(sha256(file.read_bytes()).hexdigest(), hashes[source])

    def test_reference_only_and_mockup_artifacts_are_excluded(self):
        self.assertFalse((ROOT / "reference-only").exists())
        self.assertFalse((ROOT / "assets" / "social").exists())
        self.assertFalse((ROOT / "assets" / "mockups").exists())


class BrandingWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        apply_fxd_theme(cls.application)

    def test_theme_and_approved_icons_load_at_application_scope(self):
        self.assertIn("QMainWindow", self.application.styleSheet())
        self.assertFalse(application_icon().isNull())
        self.assertFalse(icon("import-step").isNull())
        self.assertTrue(asset_path("fxd_ui", "theme", "fxd.qss").is_file())

    def test_source_badge_exposes_exact_read_only_identity_and_full_digest(self):
        badge = SourceCadBadge()
        digest = "a" * 64
        badge.set_source("assembly.step", digest, verified=True)
        self.assertIn("SOURCE CAD \u00b7 READ-ONLY", badge.text())
        self.assertIn("assembly.step", badge.text())
        self.assertIn(digest, badge.toolTip())
        self.assertNotIn("Save source", badge.text())

    def test_status_chip_pairs_semantic_icon_text_and_accessible_state(self):
        chip = StatusChip("invalid", "INVALID")
        self.assertEqual(chip.property("status"), "fail")
        self.assertEqual(chip.text_label.text(), "INVALID")
        self.assertIn("INVALID", chip.accessibleName())
        self.assertFalse(chip.icon_label.pixmap().isNull())

    def test_workflow_rail_exposes_all_steps_and_literal_state(self):
        rail = WorkflowRail()
        rail.set_states({
            "Project": "complete", "Concepts": "engineer modified",
            "Validation": "blocked",
        }, "Validation")
        self.assertEqual(rail.count(), 18)
        validation = rail.item(11)
        self.assertEqual(validation.data(Qt.ItemDataRole.UserRole + 1), "active")
        self.assertIn("Validation - Active", validation.toolTip())
        self.assertIn("Engineer Modified", rail.item(10).toolTip())

    def test_workflow_rail_single_click_navigates_once(self):
        rail = WorkflowRail()
        rail.resize(64, 320)
        rail.show()
        try:
            selected = QSignalSpy(rail.stage_selected)
            item = rail.item(1)
            QTest.mouseClick(
                rail.viewport(), Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier, rail.visualItemRect(item).center(),
            )
            self.application.processEvents()
            self.assertEqual(selected.count(), 1)
            self.assertEqual(selected.at(0)[0], "Import")
        finally:
            rail.close()

    def test_workflow_rail_keyboard_activation_navigates_once(self):
        rail = WorkflowRail()
        rail.show()
        try:
            selected = QSignalSpy(rail.stage_selected)
            rail.setCurrentRow(2)
            rail.setFocus()
            QTest.keyClick(rail, Qt.Key.Key_Return)
            self.application.processEvents()
            self.assertEqual(selected.count(), 1)
            self.assertEqual(selected.at(0)[0], "Assembly")
        finally:
            rail.close()

    def test_workflow_rail_click_activation_pair_does_not_duplicate_navigation(self):
        rail = WorkflowRail()
        selected = QSignalSpy(rail.stage_selected)
        item = rail.item(3)
        rail.itemClicked.emit(item)
        rail.itemActivated.emit(item)
        self.application.processEvents()
        self.assertEqual(selected.count(), 1)
        self.assertEqual(selected.at(0)[0], "Manufacturing Intent")

    def test_approval_gate_cannot_hide_a_blocking_result(self):
        gate = ApprovalGatePanel()
        self.assertIn("has not been run", gate.summary.text())
        gate.set_result("invalid", 2, 3, can_approve=False, approved=False)
        self.assertFalse(gate.approve.isEnabled())
        self.assertIn("2 deterministic failures", gate.summary.text())
        gate.set_result("provisional", 0, 2, can_approve=True, approved=False)
        self.assertTrue(gate.approve.isEnabled())
        self.assertIn("Provisional review", gate.summary.text())


if __name__ == "__main__":
    unittest.main()
