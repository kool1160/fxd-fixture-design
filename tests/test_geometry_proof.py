import json
import unittest

from fxd_geometry import Aabb, Box, Transform, Vec3, neutral_export


class GeometryProofTests(unittest.TestCase):
    def test_transform_and_intersection(self):
        first = Box(Vec3(10, 10, 10), Transform(Vec3(5, 0, 0))).bounds()
        second = Box(Vec3(4, 4, 4), Transform(Vec3(12, 2, 2))).bounds()
        self.assertTrue(first.intersects(second))
        self.assertEqual(first.intersection(second).minimum, Vec3(12, 2, 2))

    def test_clearance_is_measured_in_mm(self):
        first = Aabb(Vec3(0, 0, 0), Vec3(10, 10, 10))
        second = Aabb(Vec3(15, 0, 0), Vec3(20, 10, 10))
        self.assertEqual(first.clearance_to(second), 5)
        self.assertFalse(first.intersects(second))

    def test_neutral_export_is_deterministic_and_explicit(self):
        exported = json.loads(neutral_export([Box(Vec3(1, 2, 3))]))
        self.assertEqual(exported["format"], "fxd-neutral-proof-v1")
        self.assertEqual(exported["units"], "mm")
        self.assertEqual(exported["boxes"][0]["maximum"]["z"], 3)


if __name__ == "__main__":
    unittest.main()
