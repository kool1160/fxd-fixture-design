# FXD locating and constraint contract

`LocatorContact` and `LocatingStrategy` are CAD-neutral engineering inputs.
Each contact identifies a product reference, an explicit point in millimetres,
and a contact normal. A round pin contributes two radial constraints, a
diamond pin contributes one unless explicit directions are supplied, and rests
and stops contribute their explicit normal. Clamps are recorded as force
application but never count as locating constraints.

The solver forms rigid-body rows `[direction, point x direction]` and performs
deterministic rank analysis over six translational/rotational degrees of
freedom. It reports underconstraint and incremental redundant locators as
errors. Full rank is necessary but not sufficient for a production fixture:
tolerance, repeatability, datum assumptions, contact force, access, and
manufacturing validation remain explicit engineering responsibilities.

Normals are evidence supplied by a geometry-aware caller; the solver does not
invent them from AABBs. References are checked against the immutable normalized
product model. An explicit invalid strategy is an invalid fixture concept and
cannot be recommended or exported.

Evidence: `python scripts/constraint_proof.py` and
`python -m unittest discover -s tests`.
