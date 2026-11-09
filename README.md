# Personal-Blog-Studio

Blog authoring studio and blog read API (not public: approved callers with an Entra token only).

- **Studio:** WYSIWYG editor (maths, code, images, video), AI writing agent (read-aloud audio comes later). Behind Azure Easy Auth, owner only.
- **Read API:** versioned (`v1`), documented with OpenAPI, not public. Clients are separate apps.
- **Storage:** posts, media and audio live in private Azure storage, never in this repo.

Status: backend and frontend skeletons (health endpoints, Dockerfiles, CI). The system design is the workspace spec `2026-11-08-blog-studio.md`; the editor, content model and read API are not built yet.

## Repo setup

- CI: `.github/workflows/ci.yml` (`workflow-lint`, `backend-test`, `backend-lint`, `frontend-test`, `frontend-checks`) on pull requests; run `./scripts/ci-local.sh` before opening for review.
- AI PR review: `.github/workflows/claude-review.yml`, secret `CLAUDE_CODE_OAUTH_TOKEN`.
- `main` accepts changes through pull requests only.
- Azure: `DEPLOYMENT.md` (Bicep in `infra/`, image and storage scripts in `scripts/`). The infrastructure code, the Entra setup scripts and the custom-domain script exist; the studio and the read API are deployed on their default hostnames.
