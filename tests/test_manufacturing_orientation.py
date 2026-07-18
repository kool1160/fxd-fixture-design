from dataclasses import replace
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from fxd_geometry import (
    GeometryReference,
    ManufacturingOrientationError,
    OcpKernel,
    OrientationMethod,
    ReferencePlane,
    Vec3,
    load_step_for_workbench,
    orientation_from_face,
    orientation_from_faces,
    orientation_from_plane,
    recommend_orientations,
    reference_plane_orientation,
    source_orientation,
)


class ManufacturingOrientationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel = OcpKernel()
        cls.directory = tempfile.TemporaryDirectory()
        cls.source = Path(cls.directory.name) / "orientation.step"
        cls.source.write_bytes(cls.kernel.export_step(cls.kernel.make_box((0, 0, 0), (120, 80, 24))))
        cls.original = cls.source.read_bytes()
        cls.document = load_step_for_workbench(cls.source)
        cls.component = cls.document.assembly.components[0]
        cls.face = next(face for face in cls.component.faces if face.is_planar)
        cls.reference = GeometryReference(
            cls.component.reference, "body:" + __import__("hashlib").sha256(
                cls.component.reference.encode()
            ).hexdigest()[:20], cls.face.reference,
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_source_and_manufacturing_transforms_are_exact_inverses(self):
        orientation = reference_plane_orientation(
            self.document.source_sha256, ReferencePlane.TOP, rotation_degrees=90.0, accepted=True,
        )
        point = Vec3(12.5, -7.0, 3.0)
        transformed = orientation.source_point_to_manufacturing(point)
        restored = orientation.manufacturing_point_to_source(transformed)
        self.assertAlmostEqual(restored.x, point.x)
        self.assertAlmostEqual(restored.y, point.y)
        self.assertAlmostEqual(restored.z, point.z)
        self.assertEqual(orientation.manufacturing_z_source, Vec3(0.0, 0.0, 1.0))
        self.assertAlmostEqual(orientation.manufacturing_x_source.y, -1.0)

    def test_face_selection_flip_and_quarter_rotations_are_explicit(self):
        base = orientation_from_face(self.document, self.reference, accepted=True)
        flipped = orientation_from_face(self.document, self.reference, flip_normal=True, accepted=True)
        self.assertAlmostEqual(
            base.manufacturing_z_source.x * flipped.manufacturing_z_source.x
            + base.manufacturing_z_source.y * flipped.manufacturing_z_source.y
            + base.manufacturing_z_source.z * flipped.manufacturing_z_source.z,
            -1.0,
        )
        axes = {
            tuple(round(value, 6) for value in (
                orientation_from_face(self.document, self.reference, rotation_degrees=degrees,
                                      accepted=True).manufacturing_x_source.x,
                orientation_from_face(self.document, self.reference, rotation_degrees=degrees,
                                      accepted=True).manufacturing_x_source.y,
                orientation_from_face(self.document, self.reference, rotation_degrees=degrees,
                                      accepted=True).manufacturing_x_source.z,
            ))
            for degrees in (0.0, 90.0, 180.0, 270.0)
        }
        self.assertEqual(len(axes), 4)

    def test_sideways_and_upside_down_source_axes_remain_separate_from_manufacturing_truth(self):
        sideways = orientation_from_plane(
            source_sha256=self.document.source_sha256, method=OrientationMethod.SELECT_REFERENCE_PLANE,
            reference_plane=ReferencePlane.RIGHT, plane_origin_mm=Vec3(0, 0, 0),
            plane_normal_source=Vec3(1, 0, 0), accepted=True,
        )
        upside_down = orientation_from_plane(
            source_sha256=self.document.source_sha256, method=OrientationMethod.SELECT_REFERENCE_PLANE,
            reference_plane=ReferencePlane.TOP, plane_origin_mm=Vec3(0, 0, 0),
            plane_normal_source=Vec3(0, 0, -1), accepted=True,
        )
        self.assertEqual(sideways.manufacturing_z_source, Vec3(1.0, 0.0, 0.0))
        self.assertEqual(upside_down.manufacturing_z_source, Vec3(0.0, 0.0, -1.0))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_round_trip_and_source_mismatch_fail_closed(self):
        orientation = orientation_from_face(self.document, self.reference, accepted=True)
        restored = type(orientation).from_dict(orientation.to_dict())
        self.assertEqual(restored, orientation)
        with self.assertRaisesRegex(ManufacturingOrientationError, "different source"):
            orientation.require_accepted_for("f" * 64)

    def test_auto_recommendations_are_ranked_but_never_accepted(self):
        recommendations = recommend_orientations(self.document)
        self.assertTrue(recommendations)
        self.assertTrue(all(not item.orientation.accepted for item in recommendations))
        self.assertEqual(
            tuple(item.score for item in recommendations),
            tuple(sorted((item.score for item in recommendations), reverse=True)),
        )
        self.assertTrue(all(item.reasons and item.assumptions for item in recommendations))

    def test_source_orientation_requires_explicit_acceptance(self):
        orientation = source_orientation(self.document.source_sha256)
        self.assertFalse(orientation.accepted)
        self.assertTrue(orientation.with_acceptance(True).accepted)

    def _reference_for_normal(self, normal: tuple[float, float, float]) -> GeometryReference:
        face = next(face for face in self.component.faces if all(
            abs(actual - expected) < 1e-7
            for actual, expected in zip(face.normal, normal)
        ))
        return GeometryReference(
            self.component.reference,
            "body:" + sha256(self.component.reference.encode()).hexdigest()[:20],
            face.reference,
        )

    def test_two_face_guided_orientation_derives_right_handed_manufacturing_frame(self):
        bottom = self._reference_for_normal((0.0, 0.0, -1.0))
        front = self._reference_for_normal((0.0, -1.0, 0.0))
        orientation = orientation_from_faces(
            self.document, bottom, front, flip_bottom=True, accepted=True,
        )
        self.assertEqual(orientation.selected_reference, bottom)
        self.assertEqual(orientation.front_reference, front)
        self.assertEqual(orientation.manufacturing_z_source, Vec3(0.0, 0.0, 1.0))
        self.assertEqual(orientation.operator_front_source, Vec3(0.0, -1.0, 0.0))
        self.assertEqual(orientation.manufacturing_x_source, Vec3(-1.0, 0.0, 0.0))
        point = Vec3(11.0, 7.0, 3.0)
        self.assertEqual(
            orientation.manufacturing_point_to_source(
                orientation.source_point_to_manufacturing(point)
            ),
            point,
        )
        self.assertEqual(type(orientation).from_dict(orientation.to_dict()), orientation)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_two_face_guided_orientation_rejects_parallel_bottom_and_front(self):
        bottom = self._reference_for_normal((0.0, 0.0, -1.0))
        parallel_front = self._reference_for_normal((0.0, 0.0, 1.0))
        with self.assertRaisesRegex(ManufacturingOrientationError, "parallel"):
            orientation_from_faces(self.document, bottom, parallel_front)

    def test_flipping_bottom_side_reverses_guided_up_without_changing_source(self):
        bottom = self._reference_for_normal((0.0, 0.0, -1.0))
        front = self._reference_for_normal((1.0, 0.0, 0.0))
        first = orientation_from_faces(self.document, bottom, front)
        flipped = orientation_from_faces(self.document, bottom, front, flip_bottom=True)
        dot = sum(
            left * right for left, right in zip(
                first.manufacturing_z_source.__dict__.values(),
                flipped.manufacturing_z_source.__dict__.values(),
            )
        )
        self.assertAlmostEqual(dot, -1.0)
        self.assertEqual(self.source.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
