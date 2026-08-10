#!/usr/bin/env bash
set -euo pipefail

required_files=(
  README.md
  NOTICE.md
  AGENTS.md
  CURRENT.md
  BACKLOG.md
  requirements-kernel.txt
  requirements-desktop.txt
  docs/PRODUCT_DIRECTION.md
  docs/OPERATOR_PROTOCOL.md
  docs/ENGINEERING_CONSTITUTION.md
  docs/AI_DRIVEN_SYNTHESIS_ARCHITECTURE.md
  docs/ARCHITECTURE.md
  docs/ENGINEERING_TEAM.md
  docs/MILESTONE_CONTRACT.md
  docs/MILESTONE_STATE.json
  docs/decisions/0001-ai-driven-fixture-synthesis-reset.md
  scripts/validate_milestones.py
  .github/codex/prompts/run-milestone.md
  .github/codex/schemas/planning-handoff.schema.json
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "Missing required file: $file" >&2; exit 1; }
done

# The legacy milestone validator remains active until Issue #66's dedicated
# registry migration replaces or retires the pre-reset M32 projection. It must
# never be interpreted as permission to reopen superseded Issue #57 / PR #54.
python scripts/validate_milestones.py
python -m pip install --disable-pip-version-check --only-binary=:all: -r requirements-desktop.txt
node scripts/fxd-backlog.mjs validate
python -m json.tool .github/codex/schemas/planning-handoff.schema.json >/dev/null
python -m unittest discover -s tests >/dev/null
python -u scripts/kernel_proof.py

if grep -RInE '(sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY=.+)' \
  --exclude-dir=.git --exclude-dir=.venv \
  --exclude='*.md' --exclude='ci.sh' --exclude='ci-contract.sh' .; then
  echo 'Potential committed secret detected.' >&2
  exit 1
fi

echo 'FXD repository checks passed.'
