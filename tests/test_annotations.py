import tempfile
import unittest
from pathlib import Path

from fxd_geometry import (AnnotationError, Assumption, CriticalCharacteristic,
                          EngineeringAnnotations, GeometryReference, Vec3, WeldJoint,
                          import_step)


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.product = import_step(Path("tests/fixtures/synthetic_assembly.step"))
        self.face = GeometryReference("BRACKET_A", "BRACKET_BODY", face_identity="TOP_FACE")

    def test_annotations_are_separate_traceable_and_round_trip(self):
        annotations = EngineeringAnnotations.for_product(
            self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0),
            process_type="manual MIG", production_quantity=25,
        )
        annotations = EngineeringAnnotations(
            **{**annotations.__dict__,
               "critical_characteristics": (CriticalCharacteristic("datum height", (self.face,), 30, "mm", .2),),
               "permitted_locating_surfaces": (self.face,),
               "forbidden_contact_areas": (GeometryReference("BRACKET_B", "BRACKET_BODY", edge_identity="EDGE_A"),),
               "weld_joints": (WeldJoint("W1", (self.face,), "MIG"),),
               "shop_constraints": ("laser cut before machining",),
               "assumptions": (Assumption("load_direction_confirmed", "no", "Awaiting process review"),)})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annotations.json"
            annotations.save(path, self.product)
            loaded = EngineeringAnnotations.load(path, self.product)
        self.assertEqual(loaded, annotations)
        self.assertEqual(self.product.source_bytes, Path("tests/fixtures/synthetic_assembly.step").read_bytes())

    def test_unknown_geometry_and_wrong_source_are_rejected(self):
        annotations = EngineeringAnnotations.for_product(self.product, build_orientation=Vec3(0, 0, 1), loading_direction=Vec3(1, 0, 0), process_type="MIG", production_quantity=1)
        bad = EngineeringAnnotations(**{**annotations.__dict__, "permitted_locating_surfaces": (GeometryReference("missing"),)})
        with self.assertRaisesRegex(AnnotationError, "unknown component"):
            bad.validate_references(self.product)
        with self.assertRaisesRegex(AnnotationError, "different source"):
            annotations.validate_references(import_step("DATA;\n#1=PRODUCT('A','A','','');\n#2=SI_UNIT(.MILLI.,.METRE.);\n#3=FXD_INSTANCE('I','A','',0,0,0);\n"))


if __name__ == "__main__":
    unittest.main()
