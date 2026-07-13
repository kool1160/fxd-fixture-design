# FXD fixture primitive contract

Milestone 4 adds `generate_fixture_primitives`, a deterministic proof-layer
generator that consumes an immutable `ProductModel` and separate
`EngineeringAnnotations` and returns an editable `FixtureConcept`.

Each generated `FixtureFeature` contains:

- a stable concept-local identity and primitive kind;
- an AABB representation in explicit millimetres;
- source component/body references;
- the deterministic rule name and numeric parameters;
- assumptions and warnings.

The starter set is a flat baseplate, one support pad per physical body, a hard
stop aligned to the dominant loading-direction axis, a primary round-pin
envelope, and a relieved-locator envelope. Manufacturing allowance and
contact clearance are explicit `FixtureParameters`; they are not inferred.

The proof reports missing locating intent, forbidden contacts, baseplate unload
trapping, and obvious non-contact overlap findings. A support or locator may
touch its referenced product body by design. These checks are conservative
AABB evidence only: they do not provide B-Rep topology, force, tolerance-stack,
weld-access, or production-release validation. Human engineering approval is
required before use.
