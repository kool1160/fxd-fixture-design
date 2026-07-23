"""Public NIST AP242 regression coverage for exact product-feature evidence."""

from pathlib import Path
import unittest

from fxd_geometry import OcpKernel, load_step_for_workbench, product_from_workbench_document


class NistAp242FeatureEvidenceTests(unittest.TestCase):
    """The merged public pack exercises real planar and cylindrical topology."""

    @classmethod
    def setUpClass(cls):
        cls.root = (
            Path(__file__).resolve().parents[1]
            / "data" / "reference_parts" / "nist_pack_001"
        )
        cls.parts = tuple(sorted(cls.root.glob("FXD-RP-*/*.stp")))
        cls.kernel = OcpKernel()

    def test_all_ten_nist_parts_expose_deterministic_exact_face_evidence(self):
        self.assertEqual(len(self.parts), 10)
        for part in self.parts:
            with self.subTest(part=part.parent.name):
                shape = self.kernel.import_step(part)
                first = self.kernel.face_records(shape)
                second = self.kernel.face_records(shape)
                self.assertEqual(first, second)
                self.assertTrue(first)
                self.assertTrue(any(face.is_planar for face in first))
                self.assertTrue(all(face.area_mm2 > 0.0 for face in first))
                self.assertTrue(all(len(face.center_mm) == 3 for face in first))
                self.assertTrue(all(len(face.normal) == 3 for face in first))
                cylinders = tuple(
                    face for face in first if "Cylinder" in face.surface_type
                )
                self.assertTrue(cylinders)
                self.assertTrue(all(
                    face.axis_origin_mm is not None
                    and face.axis_direction is not None
                    and face.radius_mm is not None
                    and face.radius_mm > 0.0
                    for face in cylinders
                ))

    def test_workbench_normalization_preserves_face_mesh_and_axis_evidence(self):
        document = load_step_for_workbench(self.parts[0])
        product = product_from_workbench_document(document)
        faces = tuple(
            face
            for component in product.components
            for body in component.bodies
            for face in body.faces
        )
        self.assertTrue(faces)
        self.assertTrue(all(
            face.center_mm is not None
            and face.normal is not None
            and face.area_mm2 is not None
            and face.bounds is not None
            and face.mesh_evidence_digest is not None
            and face.contact_points_mm
            for face in faces
        ))
        cylinders = tuple(
            face for face in faces if "Cylinder" in face.surface_type
        )
        self.assertTrue(cylinders)
        self.assertTrue(all(
            face.axis_origin_mm is not None
            and face.axis_direction is not None
            and face.radius_mm is not None
            for face in cylinders
        ))


if __name__ == "__main__":
    unittest.main()
