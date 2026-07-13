import unittest

from fxd_geometry import StepImportError, Vec3, import_step


STEP = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('FXD synthetic assembly'),'2;1');
ENDSEC;
DATA;
#1=PRODUCT('ROOT','Root assembly','','');
#2=PRODUCT('BRACKET','Repeated bracket','','');
#3=SI_UNIT(.MILLI.,.METRE.);
#4=FXD_BODY('BRACKET_BODY','BRACKET',0,0,0,10,20,5);
#5=FXD_FACE('BRACKET_BODY','TOP_FACE');
#6=FXD_EDGE('BRACKET_BODY','EDGE_A');
#7=FXD_INSTANCE('ROOT_I','ROOT','',0,0,0);
#8=FXD_INSTANCE('BRACKET_A','BRACKET','ROOT_I',10,20,30);
#9=FXD_INSTANCE('BRACKET_B','BRACKET','ROOT_I',100,0,0);
#10=FXD_INSTANCE('NESTED','BRACKET','BRACKET_A',1,2,3);
ENDSEC;
END-ISO-10303-21;
"""


class StepImportTests(unittest.TestCase):
    def test_repeated_nested_instances_and_normalized_bounds(self):
        model = import_step(STEP, source_name="synthetic.step")
        self.assertEqual(model.units, "mm")
        self.assertEqual([component.identity for component in model.components], ["ROOT_I", "BRACKET_A", "BRACKET_B", "NESTED"])
        nested = model.components[-1]
        self.assertEqual(nested.transform.translation, Vec3(11, 22, 33))
        self.assertEqual(nested.bounds.minimum, Vec3(11, 22, 33))
        self.assertEqual(nested.bounds.maximum, Vec3(21, 42, 38))
        self.assertEqual(len(nested.bodies[0].faces), 1)
        self.assertEqual(len(nested.bodies[0].edges), 1)
        self.assertEqual(model.components[1].source_product_identity, model.components[2].source_product_identity)

    def test_source_is_immutable_and_hash_bound(self):
        model = import_step(STEP)
        with self.assertRaises(Exception):
            model.components = ()
        self.assertEqual(model.source_bytes.decode(), STEP)
        self.assertEqual(len(model.source_sha256), 64)

    def test_malformed_and_unsupported_input_fail_clearly(self):
        with self.assertRaisesRegex(StepImportError, "SI_UNIT"):
            import_step("DATA;\n#1=PRODUCT('A','A','','');\nENDSEC;")
        with self.assertRaisesRegex(StepImportError, "unsupported STEP entity"):
            import_step("DATA;\n#1=SPHERE(1);\nENDSEC;")


if __name__ == "__main__":
    unittest.main()
