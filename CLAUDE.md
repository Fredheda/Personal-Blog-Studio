# CLAUDE.md

Repo-specific facts. Everything else (response style, git and worktrees, tickets and tiers, deploys, PR size, test first, the PR loop, tooling, Jira, specs and plans) is in the workspace `CLAUDE.md` (`../CLAUDE.md`). Keep this file true.

PR titles and descriptions never mention Claude Code.

- **Merging:** the owner merges, except the bot and docs classes in the workspace `CLAUDE.md` (Git), which the coordinator merges.

## What this is

Blog authoring studio (editor, AI writing agent; read-aloud audio comes later) behind Easy Auth, plus the blog read API, which is not public: only approved callers with an Entra token can use it. Posts, media and audio live in private Azure storage, never in this repo. The backend has the content model, blob storage layer, studio post service, studio post routes and the read API routes; the studio frontend lists, creates, edits and publishes posts (plain Markdown textarea; the WYSIWYG editor is BLOG-30). The rest of the studio UI follows the system spec at `../docs/shared/specs/2026-11-08-blog-studio.md` (workspace root). Overview: `README.md`.

## Azure

`DEPLOYMENT.md` has the resources, the order of operations and the gotchas. These commands change shared production state: run them only on the owner's explicit yes for that run.

| Task | Command |
|------|---------|
| Build images (ACR Tasks) | `./scripts/build-push.sh [full-sha]` |
| Shared storage setup (dry run; `--apply` changes the shared account) | `./scripts/setup-storage.sh [--apply]` |
| Provision or update Azure (needs built images and `.env`) | `./infra/deploy.sh <full-sha>` |
| Entra apps for the two APIs, `Blog.Read`, gate callers (dry run; `--apply` writes to Entra) | `./scripts/setup-api-auth.sh [--apply]` |
| Entra login app, owner assignment, client secret (`--rotate` replaces the secret) | `./scripts/setup-easyauth.sh [--apply] [--rotate]` |
| Approve one more read API caller by client ID | `./scripts/approve-client.sh <client-id> [--apply]` |
| Three-step live gate (adds then removes temporary credentials) | `./scripts/live-gate.sh [--run]` |
| Studio custom domain: DNS records at GoDaddy (`dns`), hostname bind with a managed certificate (`bind`); dry run unless `--apply` | `./scripts/bind-domain.sh dns\|bind [--apply]` |
| Deploy code: manual workflow, the owner approves the run (rollback = older SHA) | `gh workflow run deploy.yml --ref main [-f sha=<full-sha>]` |
| Laptop fallback for the same (clean tree) | `./scripts/ship.sh` |
| One-time GitHub OIDC setup: identities, roles, `production` environment, secrets (dry run; `--apply` writes) | `./scripts/setup-github-deploy.sh [--apply]` |
| Registry purge: lock running tags, weekly task for this project's repositories (dry run; `--apply` writes) | `./scripts/setup-acr-purge.sh [--apply]` |
| Compile the Bicep (local, no login) | `az bicep build --file infra/main.bicep --stdout >/dev/null` |

- Script tests use a fake `az` (`backend/tests/conftest.py`); the Bicep is checked structurally (`backend/tests/test_infra_bicep.py`). Check shell scripts with `shellcheck -x -P SCRIPTDIR`.
- The read API identity has no role on `blog-drafts` and no write role anywhere; `approvedClientIds` cannot be empty; no auth config is conditional. Tests pin all three.
- `deploy.sh` reads the git-ignored `.env` (names in `.env.example`; the Entra scripts write the IDs and the Easy Auth secret) and needs an explicit full SHA whose images exist. Secrets reach `az`, `curl` and `jq` only through mode-600 temporary files or the environment, never through arguments.
- The Entra scripts are dry runs unless given `--apply` (`--run` for the gate) and re-apply every property on each run. Run them only on the owner's explicit yes for that run.
- Code deploys go through the Deploy workflow (`production` environment, owner approval), infra through `deploy.sh`. `redeploy.sh <sha>` and `ship.sh` change production too: owner's yes for each run. Never approve a waiting deployment.
- The web app's custom domain is declared in the Bicep from `BLOG_WEB_CUSTOM_DOMAIN` and `BLOG_WEB_CERTIFICATE_NAME` (written by `bind-domain.sh`); `deploy.sh` refuses a deploy that would unbind it.

## Commands

Python 3.13 with Poetry 2 (backend); Node 24 with npm 12.2.2 (frontend, Next.js 16). Run from the repo root unless noted.

| Task | Command |
|------|---------|
| Install | `cd backend && poetry install` |
| Tests | `cd backend && poetry run pytest -v` |
| Lint, format check, types | `cd backend && poetry run ruff check . && poetry run ruff format --check . && poetry run pyright` |
| Frontend install | `cd frontend && npm ci` |
| Frontend tests | `cd frontend && npm test` |
| Frontend lint, build, types | `cd frontend && npm run lint && npm run build && npx tsc --noEmit` (the build writes `next-env.d.ts`, which tsc needs) |
| All CI checks | `./scripts/ci-local.sh` (the gate before `gh pr ready`) |

CI (`.github/workflows/ci.yml`) runs `workflow-lint`, `backend-test`, `backend-lint`, `frontend-test` and `frontend-checks` on pull requests only; a push to `main` runs no CI, because the PR already ran it. Images are built on demand by the Deploy workflow, never by CI.

## Gotchas

- Public repo: never commit post content, media, audio, keys or `.env` files. `.gitignore` carries the baseline.
- The read API is not public. Nothing client-specific (Portfolio or otherwise) belongs in this repo.
- `backend/` holds one Poetry project and two images. `Dockerfile.blogapi` copies `blog_core` and `blog_api` only; the read-API process must never import studio code or agent/LLM libraries (`backend/tests/test_apps.py` and `backend/tests/test_dockerfiles.py` pin both).
- `blog_core` also holds ids (`ids.py`), blob paths (`layout.py`), stored-document models (`models.py`) and the `BlobStore` interface (`store.py`). `AzureBlobStore` is the production store (managed identity); `tests/fake_blob_store.py` is the unit-test store. Every blob path comes from `layout.py`. Change the store or the fake only together with `tests/test_store_contract.py`, and rerun it against Azurite (`DEPLOYMENT.md`, "Storage tests against Azurite").
- Markdown parsing (`markdown-it-py`, `mdit-py-plugins`) is in Poetry group `studio`, installed by `Dockerfile.studio` only; `studio_api.markdown.validate_body` is the publish-time check (no raw HTML, `https:`/`#anchor`/relative links only). `studio_api.posts.PostService` holds no state; publish writes the snapshot first and `index.json` last.
- Studio routes (`studio_api/routes.py`) are a thin layer over `PostService`; every non-GET needs header `X-Blog-Studio: 1` (and a listed `Origin` when `BLOG_STUDIO_ORIGINS` is set); body, meta, restore and publish need `If-Match`. Errors are problem+json (`blog_core.problem`). `openapi/v1.json` is the read API `v1` contract with examples.
- The read API (`blog_api`) serves `/v1` from `blog-published` only. The platform validates the token and injects `X-MS-CLIENT-PRINCIPAL`; `blog_api/principal.py` checks the `Blog.Read` role from it (401 without a principal, 403 without the role), so platform authentication must stay enabled. Media links are 10-minute read-only user-delegation SAS (`blog_api/media.py`). `openapi/v1.json` must match the generated schema (`tests/test_openapi_contract.py`); a contract change needs a `docs/api-changelog.md` entry and the new `info.version`.
- Apps are built through `blog_core.app_factory.create_base_app`: interactive docs and OpenAPI are off unless an app passes its own `openapi_url`. It also caps every request body at 1 MiB (413 problem+json, also for a chunked body: reading stops past the cap and the app's own answer, a framework 400 included, is replaced by the 413) and answers unknown paths and wrong methods with problem+json (`backend/tests/test_base_app.py`).
- The browser reaches the studio API only through the web app's route handler `/api/studio/...` (`frontend/lib/proxy.ts`): `/posts` allowlist, 1 MiB cap, bearer token from the web app's managed identity, the browser's `X-Blog-Studio` and `Origin` forwarded unchanged and never added by the proxy, no CORS headers and no OPTIONS handler (Next's automatic OPTIONS only sets `Allow`, so a cross-origin preflight still fails). Keep it that way: the studio API's same-origin guard relies on it.
- **Next.js 16 and React 19 are newer than most training data.** Read the guide under `frontend/node_modules/next/dist/docs/` before writing frontend code.
- npm is pinned to 12.2.2 in every Dockerfile stage and every CI job that uses `actions/setup-node` (needs Node `^24.15.0`; `backend/tests/test_npm_pin.py` enforces one version everywhere). npm 12 blocks dependency install scripts unless `frontend/package.json` `allowScripts` lists them; approve a needed script with `npm install-scripts approve <pkg>`.
- Fonts are system stacks only: no font file, `@font-face` or `next/font` (owner rule; `frontend/tests/hardening.test.ts` enforces it). Maths renders as MathML, never with bundled maths fonts.
- `next dev` writes untracked `frontend/AGENTS.md` and `frontend/CLAUDE.md` when it detects an AI agent. Delete them, or start with `env -u AI_AGENT -u CLAUDECODE`.
- `GET /healthz` (both apps) is the path Easy Auth and token validation exclude; keep it free of data.

## Security checks

`.github/workflows/security.yml` runs `gitleaks` on every push to a PR and `bandit` (HIGH only) once the PR is ready, plus advisory `pip-audit`, `npm-audit` and CodeQL (findings in the Security tab) on ready PRs and weekly (Mondays); `gh workflow run security.yml --ref main` runs it on demand. Workflow linting is the `workflow-lint` job of `ci.yml`. Run a check locally:

| Check | Command |
|---|---|
| Secrets | `docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --redact --no-banner --verbose` |
| Python, HIGH severity | `pipx run bandit==1.9.4 -r backend/blog_core backend/studio_api backend/blog_api -lll` |
| Python dependencies | `cd backend && poetry run pip install pip-audit==2.10.1 && poetry run pip-audit --local` |
| Frontend dependencies | `cd frontend && npm audit --omit=dev --audit-level=high` |

Dependabot (`.github/dependabot.yml`) opens weekly PRs: one grouped PR per ecosystem for minor and patch updates, majors separate, only releases older than 14 days; the Node 24 and Python 3.13 images are left to hand. Alerts and security updates are repo settings. Dependabot PRs get no secrets, so the AI review skips them.

## AI PR review

`.github/workflows/claude-review.yml` reviews each PR once it is ready, on later pushes, and when the owner comments `@claude`. Secret: `CLAUDE_CODE_OAUTH_TOKEN` (repo secret; expires about 2027-11). Fallback if subscription auth is refused: use `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}` in both jobs. Fork and Dependabot PRs are skipped. Do not require the `Claude Review` job as a status check: it skips on PRs that change the workflow file.

The `main` ruleset (`main-protect`) blocks deletion and force-push and requires a PR with 0 approvals; it requires the CI checks `workflow-lint`, `backend-test`, `backend-lint`, `frontend-test` and `frontend-checks`, and the security checks `gitleaks` and `bandit` (`pip-audit`, `npm-audit` and `codeql` are advisory). `bandit` is skipped on a draft PR, which counts as passing.
