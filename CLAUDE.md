# CLAUDE.md

Repo-specific facts. Everything else (response style, git and worktrees, tickets and tiers, deploys, PR size, test first, the PR loop, tooling, Jira, specs and plans) is in the workspace `CLAUDE.md` (`../CLAUDE.md`). Keep this file true.

PR titles and descriptions never mention Claude Code.

- **Merging:** the owner merges, except the bot and docs classes in the workspace `CLAUDE.md` (Git), which the coordinator merges.

## What this is

Blog authoring studio (editor, AI writing agent; read-aloud audio comes later) behind Easy Auth, plus the blog read API, which is not public: only approved callers with an Entra token can use it. Posts, media and audio live in private Azure storage, never in this repo. The backend skeleton exists (health endpoints only); the studio UI, content model and read API follow the system spec at `../docs/shared/specs/2026-11-08-blog-studio.md` (workspace root). Overview: `README.md`.

## Azure

`DEPLOYMENT.md` has the resources, the order of operations and the gotchas. These commands change shared production state: run them only on the owner's explicit yes for that run.

| Task | Command |
|------|---------|
| Build images (ACR Tasks) | `./scripts/build-push.sh [full-sha]` |
| Shared storage setup (dry run; `--apply` changes the shared account) | `./scripts/setup-storage.sh [--apply]` |
| Provision or update Azure (needs built images and `.env`) | `./infra/deploy.sh <full-sha>` |
| Compile the Bicep (local, no login) | `az bicep build --file infra/main.bicep --stdout >/dev/null` |

- Script tests use a fake `az` (`backend/tests/conftest.py`); the Bicep is checked structurally (`backend/tests/test_infra_bicep.py`). Check shell scripts with `shellcheck -x -P SCRIPTDIR`.
- The read API identity has no role on `blog-drafts` and no write role anywhere; `approvedClientIds` cannot be empty; no auth config is conditional. Tests pin all three.
- `deploy.sh` needs the Entra IDs from the setup scripts (BLOG-15) in the git-ignored `.env` (names in `.env.example`) and an explicit full SHA whose images exist.

## Commands

Python 3.13, Poetry 2. Run from the repo root unless noted.

| Task | Command |
|------|---------|
| Install | `cd backend && poetry install` |
| Tests | `cd backend && poetry run pytest -v` |
| Lint, format check, types | `cd backend && poetry run ruff check . && poetry run ruff format --check . && poetry run pyright` |
| All CI checks | `./scripts/ci-local.sh` (the gate before `gh pr ready`) |

CI (`.github/workflows/ci.yml`) runs `workflow-lint`, `backend-test` and `backend-lint` on pull requests only; a push to `main` runs no CI, because the PR already ran it.

## Gotchas

- Public repo: never commit post content, media, audio, keys or `.env` files. `.gitignore` carries the baseline.
- The read API is not public. Nothing client-specific (Portfolio or otherwise) belongs in this repo.
- `backend/` holds one Poetry project and two images. `Dockerfile.blogapi` copies `blog_core` and `blog_api` only; the read-API process must never import studio code or agent/LLM libraries (`backend/tests/test_apps.py` and `backend/tests/test_dockerfiles.py` pin both).
- Apps are built through `blog_core.app_factory.create_base_app`: interactive docs and OpenAPI are off unless an app passes its own `openapi_url`.

## AI PR review

`.github/workflows/claude-review.yml` reviews each PR once it is ready, on later pushes, and when the owner comments `@claude`. Secret: `CLAUDE_CODE_OAUTH_TOKEN` (repo secret; expires about 2027-11). Fallback if subscription auth is refused: use `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}` in both jobs. Fork and Dependabot PRs are skipped. Do not require the `Claude Review` job as a status check: it skips on PRs that change the workflow file.

The `main` ruleset (`main-protect`) blocks deletion and force-push and requires a PR with 0 approvals; it requires the CI checks `workflow-lint`, `backend-test` and `backend-lint`.
