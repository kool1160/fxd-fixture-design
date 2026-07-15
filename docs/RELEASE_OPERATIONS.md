# FXD release and local operations

FXD releases are engineering-review software releases. A release never
certifies a fixture or authorizes production.

## Reproducible local path

Use a clean checkout, Python 3.11 or newer, and the pinned dependency file:

```text
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements-kernel.txt
bash scripts/ci.sh
python scripts/performance_budget.py
```

The offline contract path is `bash scripts/ci-contract.sh`; it does not
install packages. Updating uses the same checkout, dependency pin, and
checks, followed by opening the project and rechecking its source SHA-256.

## Project operations

Projects use `fxd-neutral-project-v2`. The loader accepts v1 and reconstructs
the deterministic state before checking validation evidence. Saves are atomic.
The application writes an adjacent `.autosave` file and JSONL diagnostics under
`~/.fxd`; diagnostics contain event metadata, not source geometry. Preferences
are separate from the project and cannot contain engineering rules.

## Release evidence and signing

From a clean reviewed checkout, create a hash manifest with:

```text
python scripts/release-manifest.py 0.1.0 dist/fxd-release-manifest.json
```

An authorized release owner signs the manifest using the organization's
approved key-management system and publishes the signature beside it. FXD
does not embed private keys or claim a signature that was not produced by that
owner. The manifest and `bash scripts/ci.sh` output are retained with the
release record.
