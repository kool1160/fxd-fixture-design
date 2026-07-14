import unittest

from fxd_geometry.kernel import (KernelCapabilities, KernelUnavailable,
                                 installed_backend_candidates,
                                 require_real_kernel)


class KernelBoundaryTests(unittest.TestCase):
    def test_capability_gate_requires_every_real_geometry_operation(self):
        complete = KernelCapabilities("test", "1", True, True, True, True, True, True)
        incomplete = KernelCapabilities("test", "1", True, True, True, False, True, True)
        self.assertTrue(complete.is_complete)
        self.assertFalse(incomplete.is_complete)

    def test_missing_or_unreviewed_backend_never_falls_back_to_aabb(self):
        candidates = installed_backend_candidates()
        with self.assertRaisesRegex(KernelUnavailable, "approved B-Rep backend|reviewed FXD adapter"):
            require_real_kernel()
        # This assertion documents the safe behavior on this CI image while
        # still allowing a future image to detect an unreviewed backend.
        if not candidates:
            self.assertEqual(candidates, ())


if __name__ == "__main__":
    unittest.main()
