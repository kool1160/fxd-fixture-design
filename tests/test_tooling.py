import unittest

from fxd_geometry import (Aabb, ToolingItem, ToolingLibrary, ToolingLibraryError,
                          generic_tooling_library)


class ToolingLibraryTests(unittest.TestCase):
    def test_generic_contract_exposes_required_metadata(self):
        item = generic_tooling_library().select(
            "clamp", minimum_stroke=10, minimum_force=500, force_units="N").item
        self.assertEqual(item.units, "mm")
        self.assertEqual(item.force_units, "N")
        self.assertTrue(item.mounting and item.access)
        self.assertGreater(item.stroke, 0)
        self.assertGreater(item.force, 0)
        self.assertEqual(item.license, "FXD generic metadata")

    def test_preferred_standard_beats_custom_geometry(self):
        custom = ToolingItem("shop-clamp", "clamp", Aabb.from_values(0, 0, 0, 1, 1, 1),
                             stroke=30, force=2000, force_units="N",
                             source="private-shop", custom_geometry=True, preferred=False)
        result = ToolingLibrary((custom, *generic_tooling_library().items)).select(
            "clamp", minimum_stroke=10, minimum_force=500, force_units="N")
        self.assertEqual(result.item.identity, "generic-toggle-clamp")

    def test_force_units_are_explicit_and_not_silently_mixed(self):
        with self.assertRaisesRegex(ToolingLibraryError, "newtons"):
            ToolingItem("imperial-clamp", "clamp", Aabb.from_values(0, 0, 0, 1, 1, 1),
                        force=500, force_units="lbf")
        with self.assertRaisesRegex(ToolingLibraryError, "newtons"):
            generic_tooling_library().select("clamp", minimum_force=500, force_units="lbf")

    def test_custom_geometry_must_remain_separate(self):
        with self.assertRaises(ToolingLibraryError):
            ToolingItem("bad", "clamp", Aabb.from_values(0, 0, 0, 1, 1, 1), custom_geometry=True)

    def test_missing_capacity_is_explicit(self):
        self.assertIsNone(generic_tooling_library().select("clamp", minimum_force=5000))


if __name__ == "__main__":
    unittest.main()
