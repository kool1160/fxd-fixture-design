# FXD STEP import contract

Milestone 2 provides a dependency-free, runnable import proof for synthetic
Part 21-shaped records. The reader normalizes all geometry to millimetres and
preserves the original source bytes and SHA-256 identity.

Supported application records are:

- `PRODUCT(identity, name, ...)`
- `SI_UNIT(.MILLI., .METRE.)`
- `FXD_BODY(identity, product, min-x, min-y, min-z, max-x, max-y, max-z)`
- `FXD_FACE(body, identity)` and `FXD_EDGE(body, identity)`
- `FXD_INSTANCE(identity, product, parent, x, y, z)`

`FXD_INSTANCE` translations are composed through the parent hierarchy, so
repeated products retain separate instance identities while sharing source
product and body definitions. Assembly-container products may have no direct
body.

This is an evidence contract, not a general ISO 10303 parser. It deliberately
does not claim support for vendor STEP dialects, curved surfaces, exact B-Rep
topology, rotations, or robust kernel operations. A future reviewed OCCT
adapter must translate full STEP into the same neutral model and retain the
same explicit failure and source-immutability guarantees.

Run `python scripts/step_import_proof.py` for the reproducible proof.
