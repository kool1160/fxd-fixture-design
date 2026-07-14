import unittest

from fxd_geometry import AabbTestDouble, KernelUnavailableError, reviewed_kernel


class KernelBoundaryTests(unittest.TestCase):
    def test_aabb_is_explicitly_not_a_brep_kernel(self):
        capabilities = AabbTestDouble().capabilities
        self.assertEqual(capabilities.name, "fxd-aabb-test-double")
        self.assertFalse(capabilities.b_rep)
        self.assertFalse(capabilities.step_import)

    def test_unreviewed_kernel_fails_closed(self):
        with self.assertRaisesRegex(KernelUnavailableError, "No reviewed B-Rep kernel"):
            reviewed_kernel()

    def test_test_double_rejects_real_step_operations(self):
        with self.assertRaises(KernelUnavailableError):
            AabbTestDouble().import_step(b"ISO-10303-21;")


if __name__ == "__main__":
    unittest.main()
