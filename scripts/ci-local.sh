#!/usr/bin/env bash
# Run every check .github/workflows/ci.yml runs, locally. It is the gate before
# `gh pr ready`. A test in backend/tests keeps this file and ci.yml in step:
# every ci.yml job id appears below as a `step "<job-id>"`.
#
# Needs `poetry install` once in backend/ and `npm ci` once in frontend/, plus
# `cd frontend && npm run e2e:install` once (Chromium and the browser tests'
# Azurite; a running local Azurite must be stopped: the tests use ports 10000
# to 10002). workflow-lint uses a local `actionlint` if present, else Docker.
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
  docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 -color
fi

step "backend-test"
(cd backend && poetry run pytest -v)

step "backend-lint"
(cd backend && poetry run ruff check . && poetry run ruff format --check . && poetry run pyright)

step "storage-contract"
docker run -d --rm --name blog-ci-azurite -p 127.0.0.1:10000:10000 mcr.microsoft.com/azure-storage/azurite:3.37.0@sha256:830430c1da1a2d537e08f3e6764dd1f5ae00cf0346bcaf625b968ec3f0971fd5 \
  azurite-blob --blobHost 0.0.0.0 --inMemoryPersistence --skipApiVersionCheck >/dev/null
trap 'docker stop blog-ci-azurite >/dev/null 2>&1 || true' EXIT
timeout 30 sh -c 'until curl -s -o /dev/null http://127.0.0.1:10000; do sleep 1; done'
(cd backend && AZURITE_CONNECTION_STRING=UseDevelopmentStorage=true poetry run pytest -v tests/test_store_contract.py)
docker stop blog-ci-azurite >/dev/null

step "frontend-test"
(cd frontend && npm test)

step "frontend-checks"
(cd frontend && npm run lint && npm run build && npx tsc --noEmit)

step "frontend-e2e"
(cd frontend && npm run e2e)

echo
echo "ci-local: all checks passed."
