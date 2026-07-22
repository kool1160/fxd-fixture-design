#!/usr/bin/env bash
set -euo pipefail

required_files=(
  README.md
  NOTICE.md
  AGENTS.md
  BACKLOG.md
  requirements-kernel.txt
  requirements-desktop.txt
  docs/PRODUCT_DIRECTION.md
  docs/ENGINEERING_CONSTITUTION.md
  docs/ARCHITECTURE.md
  docs/AGENT_ROSTER.md
  docs/MILESTONE_CONTRACT.md
  docs/MILESTONE_STATE.json
  scripts/validate_milestones.py
  .github/codex/prompts/run-milestone.md
  .github/codex/schemas/planning-handoff.schema.json
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "Missing required file: $file" >&2; exit 1; }
done

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
