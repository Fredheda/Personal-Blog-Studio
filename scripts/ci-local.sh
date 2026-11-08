#!/usr/bin/env bash
# Run every check .github/workflows/ci.yml runs, locally. It is the gate before
# `gh pr ready`. A test in backend/tests keeps this file and ci.yml in step:
# every ci.yml job id appears below as a `step "<job-id>"`.
#
# Needs `poetry install` once in backend/ and `npm ci` once in frontend/. workflow-lint uses a local
# `actionlint` if present, else Docker.
#
# Usage: ./scripts/ci-local.sh
set -euo pipefail
cd "$(dirname "$0")/.."

step() {
  echo
  echo "==> $*"
}

step "workflow-lint"
if command -v actionlint >/dev/null 2>&1; then
  actionlint
else
  docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12 -color
fi

step "backend-test"
(cd backend && poetry run pytest -v)

step "backend-lint"
(cd backend && poetry run ruff check . && poetry run ruff format --check . && poetry run pyright)

step "frontend-test"
(cd frontend && npm test)

step "frontend-checks"
(cd frontend && npm run lint && npm run build && npx tsc --noEmit)

echo
echo "ci-local: all checks passed."
