# FXD release and local operations

FXD releases are engineering-review software releases. A release never
certifies a fixture or authorizes production.

## Reproducible local path

Use a clean checkout, Python 3.11 or newer, and the pinned dependency file:

```text
python -m venv .venv
. .venv/bin/activate                 # Windows: .venv\Scripts\activate
python -m pip install -r requirements-kernel.txt
bash scripts/ci.sh
python scripts/performance_budget.py
```

The offline contract path is `bash scripts/ci-contract.sh`; it does not
install packages. Updating uses the same checkout, dependency pin, and
checks, followed by opening the project and rechecking its source SHA-256.

## Project operations

Projects use `fxd-neutral-project-v2`. The loader accepts true v1 documents
without a `schema_version` field and reconstructs deterministic state before
checking validation evidence. Saves are atomic. The application writes an
adjacent `.autosave` file and JSONL diagnostics under `~/.fxd`; diagnostics
contain event metadata, not source geometry. Preferences are separate from the
project and cannot contain engineering rules.

## Performance evidence

`scripts/performance_budget.py` generates a legally shareable synthetic
assembly containing 250 repeated placed components. It measures import plus
fixture-concept generation against the documented five-second neutral budget
and fails if component identity is lost or the budget is exceeded. Real-kernel
performance evidence remains a separate GitHub Actions or authorized local
validation concern when a milestone specifically requires it.

## Release evidence and signing

Create the reviewed build artifacts first. Then pass only those explicit files
or directories to the manifest command:

```text
python scripts/release-manifest.py 0.1.0 dist/fxd-release-manifest.json dist/fxd-app.zip dist/installer
```

The manifest tool does not scan the checkout. It rejects local-only or sensitive
paths such as `.git`, `.fxd`, virtual environments, caches, and customer
folders. This prevents private CAD, diagnostics, development environments, and
unreviewed files from silently entering release evidence.

An authorized release owner signs the manifest using the organization's
approved key-management system and publishes the signature beside it. FXD
does not embed private keys or claim a signature that was not produced by that
owner. The manifest and `bash scripts/ci.sh` output are retained with the
release record.
