#!/usr/bin/env bash
set -euo pipefail

required_files=(
  README.md
  NOTICE.md
  AGENTS.md
  BACKLOG.md
  requirements-kernel.txt
  docs/PRODUCT_DIRECTION.md
  docs/ENGINEERING_CONSTITUTION.md
  docs/ARCHITECTURE.md
  docs/AGENT_ROSTER.md
  .github/codex/prompts/run-milestone.md
  .github/codex/schemas/planning-handoff.schema.json
)

for file in "${required_files[@]}"; do
  [[ -f "$file" ]] || { echo "Missing required file: $file" >&2; exit 1; }
done

node scripts/fxd-backlog.mjs validate
python -m json.tool .github/codex/schemas/planning-handoff.schema.json >/dev/null
python -m compileall -q fxd_geometry tests scripts

# Run the repository suite without attempting network installation. Tests that
# explicitly require the real OCP runtime must skip or fail closed when it is
# unavailable; neutral-boundary, application, persistence, and deterministic
# contract tests remain mandatory.
python -m unittest discover -s tests

if grep -RInE '(sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY=.+)' \
  --exclude-dir=.git --exclude='*.md' --exclude='ci.sh' --exclude='ci-contract.sh' .; then
  echo 'Potential committed secret detected.' >&2
  exit 1
fi

echo 'FXD offline contract checks passed. Real-kernel acceptance still requires GitHub Actions.'
