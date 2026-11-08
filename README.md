# Personal-Blog-Studio

Blog authoring studio and internal blog read API.

- **Studio:** WYSIWYG editor (maths, code, images, video), AI writing agent, read-aloud audio. Behind Azure Easy Auth, owner only.
- **Read API:** versioned (`v1`), documented with OpenAPI, not public. Clients are separate apps.
- **Storage:** posts, media and audio live in private Azure storage, never in this repo.

Status: baseline only (CI, AI PR review, repo settings). The system design is being specced; no application code yet.

## Repo setup

- CI: `.github/workflows/ci.yml` (`workflow-lint` for now).
- AI PR review: `.github/workflows/claude-review.yml`, secret `CLAUDE_CODE_OAUTH_TOKEN`.
- `main` accepts changes through pull requests only.
