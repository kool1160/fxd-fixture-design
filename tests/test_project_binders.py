from __future__ import annotations

import hashlib
import importlib.metadata
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from scripts import generate_project_binders as binders


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PINS = {
    "reportlab": "5.0.0",
    "pypdf": "6.14.2",
    "pillow": "12.3.0",
    "charset-normalizer": "3.4.9",
}


class ProjectBinderPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._first_temp = tempfile.TemporaryDirectory(prefix="fxd-test-binder-a-")
        cls._second_temp = tempfile.TemporaryDirectory(prefix="fxd-test-binder-b-")
        cls.first = binders.build_binders(Path(cls._first_temp.name))
        cls.second = binders.build_binders(Path(cls._second_temp.name))

    @classmethod
    def tearDownClass(cls):
        cls._second_temp.cleanup()
        cls._first_temp.cleanup()

    def test_dependency_versions_are_exact_and_match_runtime(self):
        requirements = (ROOT / "requirements-binder.txt").read_text(encoding="utf-8")
        pins = {
            line.split("==", 1)[0]: line.split("==", 1)[1]
            for line in requirements.splitlines()
            if line and not line.startswith("#")
        }
        self.assertEqual(pins, EXPECTED_PINS)
        for package, version in EXPECTED_PINS.items():
            self.assertEqual(importlib.metadata.version(package), version)

    def test_dependency_license_record_is_complete(self):
        record = (ROOT / "docs/project-records/BINDER_DEPENDENCIES.md").read_text(encoding="utf-8")
        expected = {
            "ReportLab | 5.0.0 | BSD 3-Clause",
            "pypdf | 6.14.2 | BSD 3-Clause",
            "Pillow | 12.3.0 | MIT-CMU",
            "charset-normalizer | 3.4.9 | MIT",
            "No package wheel, shared",
            "commercial use",
            "native-code redistribution",
        }
        for item in expected:
            self.assertIn(item, record)

    def test_two_independent_generations_are_byte_identical(self):
        for first, second in zip(self.first, self.second, strict=True):
            self.assertEqual(first.name, second.name)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(hashlib.sha256(first.read_bytes()).hexdigest(), hashlib.sha256(second.read_bytes()).hexdigest())

    def test_volume_outlines_include_every_section_and_milestone(self):
        expected = (
            binders.expected_volume_outline(binders.MILESTONES[:25]),
            binders.expected_volume_outline(binders.MILESTONES[25:]),
        )
        for path, expected_titles in zip(self.first[:2], expected, strict=True):
            reader = PdfReader(path)
            self.assertEqual(binders.outline_titles(reader), expected_titles)
            self.assertEqual(reader.outline[2].title, "3. Detailed Milestone Records")
            self.assertIsInstance(reader.outline[3], list)

    def test_combined_binder_preserves_volume_and_child_navigation(self):
        reader = PdfReader(self.first[2])
        self.assertEqual(reader.outline[0].title, "Volume 1 - Milestones 01-25")
        self.assertEqual(len(reader.outline[1]), 9)
        self.assertEqual(reader.outline[2].title, "Volume 2 - Milestones 26-31")
        self.assertEqual(len(reader.outline[3]), 9)
        titles = binders.outline_titles(reader)
        self.assertIn("Milestone 01 - Establish the Runnable Technical Baseline", titles)
        self.assertIn("Milestone 31 - AI Fixture Engineer and Guided Validation", titles)

    def test_metadata_dates_and_document_ids_are_stable(self):
        for first, second in zip(self.first, self.second, strict=True):
            first_reader = PdfReader(first)
            second_reader = PdfReader(second)
            self.assertEqual(first_reader.metadata.creation_date, second_reader.metadata.creation_date)
            self.assertEqual(first_reader.metadata.modification_date, second_reader.metadata.modification_date)
            self.assertEqual(first_reader.trailer["/ID"], second_reader.trailer["/ID"])

    def test_hash_manifest_matches_committed_pdf_bytes(self):
        paths = tuple(binders.OUTPUT / name for name in (binders.VOLUME_1_NAME, binders.VOLUME_2_NAME, binders.COMBINED_NAME))
        expected = "\n".join(binders.digest_lines(paths)) + "\n"
        self.assertEqual(binders.HASH_MANIFEST.read_text(encoding="utf-8"), expected)

    def test_published_pdfs_are_git_binary_artifacts(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("/docs/project-records/print/*.pdf binary", attributes)

    def test_committed_pdfs_pass_structural_preflight(self):
        binders.preflight_pdf(binders.OUTPUT / binders.VOLUME_1_NAME, binders.expected_volume_outline(binders.MILESTONES[:25]))
        binders.preflight_pdf(binders.OUTPUT / binders.VOLUME_2_NAME, binders.expected_volume_outline(binders.MILESTONES[25:]))
        combined = [
            "Volume 1 - Milestones 01-25",
            *binders.expected_volume_outline(binders.MILESTONES[:25]),
            "Volume 2 - Milestones 26-31",
            *binders.expected_volume_outline(binders.MILESTONES[25:]),
        ]
        binders.preflight_pdf(binders.OUTPUT / binders.COMBINED_NAME, combined)

    def test_audit_claims_match_repository_evidence(self):
        audit = (ROOT / "docs/project-records/AUDIT_MILESTONES_01_31.md").read_text(encoding="utf-8")
        self.assertNotIn("rendered and visually reviewed every DOCX page", audit)
        self.assertNotIn("verified embedded fonts and searchable text", audit)
        self.assertNotIn("added image alternative text to editable sources", audit)
        self.assertIn("byte-identical output", audit)
        self.assertIn("No editable DOCX sources are part", audit)

    def test_publication_contains_no_private_inputs_or_secrets(self):
        forbidden = ("OPENAI_API_KEY", "Authorization:", "C:\\Users\\", ".stp", ".step")
        for path in self.first:
            text = "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
            for value in forbidden:
                self.assertNotIn(value, text)
        source = (ROOT / "scripts/generate_project_binders.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("openai", source)
        self.assertNotIn("requests.", source)

    def test_workflow_is_pinned_tested_and_no_op_aware(self):
        workflow = (ROOT / ".github/workflows/project-binder-publication.yml").read_text(encoding="utf-8")
        self.assertIn("--requirement requirements-binder.txt", workflow)
        self.assertIn("python -m unittest -v tests.test_project_binders", workflow)
        self.assertIn("git diff --cached --quiet", workflow)
        self.assertIn('echo "Generated binder files are already current."', workflow)

    def test_publication_lane_cannot_change_product_milestone_state(self):
        workflow = (ROOT / ".github/workflows/project-binder-publication.yml").read_text(encoding="utf-8")
        staged = [line.strip() for line in workflow.splitlines() if line.strip().startswith("git add ")]
        self.assertEqual(len(staged), 4)
        self.assertTrue(all("docs/project-records/" in line for line in staged))
        readme = (ROOT / "docs/project-records/README.md").read_text(encoding="utf-8")
        self.assertIn("do not own or change current product-milestone status", readme)
        self.assertNotIn("Current / Pending", readme)


if __name__ == "__main__":
    unittest.main()
