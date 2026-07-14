import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fxd_geometry import (ApprovalRequired, ConnectorError, NeutralStepConnector,
                          connector_registry, probe_solidworks,
                          require_destructive_approval)


class ConnectorTests(unittest.TestCase):
    def test_standalone_connector_is_available_and_preserves_neutral_model(self):
        connector = NeutralStepConnector()
        product = connector.import_product(Path("tests/fixtures/synthetic_assembly.step"))
        self.assertEqual(connector.probe().status, "available")
        self.assertEqual(product.units, "mm")
        self.assertEqual(connector_registry()[0].descriptor.identity, "neutral-step")

    def test_connector_failure_does_not_mutate_or_replace_input(self):
        source = Path("tests/fixtures/synthetic_assembly.step")
        original = source.read_bytes()
        with self.assertRaisesRegex(ConnectorError, "import failed"):
            NeutralStepConnector().import_product("DATA;\n#1=NOT_SUPPORTED();")
        self.assertEqual(source.read_bytes(), original)

    def test_solidworks_probe_is_conservative_and_platform_independent(self):
        with patch("fxd_geometry.connectors.platform.system", return_value="Linux"), \
             patch.dict(os.environ, {}, clear=True):
            unsupported = probe_solidworks()
        self.assertEqual(unsupported.status, "unsupported")
        self.assertIn("No vendor SDK", " ".join(unsupported.limitations))

        with patch("fxd_geometry.connectors.platform.system", return_value="Windows"), \
             patch.dict(os.environ, {}, clear=True):
            not_detected = probe_solidworks()
        self.assertEqual(not_detected.status, "not_detected")
        self.assertIsNone(not_detected.version)

        with patch("fxd_geometry.connectors.platform.system", return_value="Windows"), \
             patch.dict(os.environ, {"FXD_SOLIDWORKS_VERSION": "2026 Connected"}, clear=True):
            unknown = probe_solidworks()
        self.assertEqual(unknown.status, "unknown")
        self.assertEqual(unknown.version, "2026 Connected")
        self.assertIn("no SDK call", " ".join(unknown.evidence))

    def test_destructive_operation_is_blocked_until_approved(self):
        with self.assertRaises(ApprovalRequired):
            require_destructive_approval("mutate_vendor_document")
        with self.assertRaises(ConnectorError):
            require_destructive_approval("unknown")
        require_destructive_approval("mutate_vendor_document", approved=True)


if __name__ == "__main__":
    unittest.main()
