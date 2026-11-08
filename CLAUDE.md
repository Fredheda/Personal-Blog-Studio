# CLAUDE.md

Repo-specific facts. Everything else (response style, git and worktrees, tickets and tiers, deploys, PR size, test first, the PR loop, tooling, Jira, specs and plans) is in the workspace `CLAUDE.md` (`../CLAUDE.md`). Keep this file true.

PR titles and descriptions never mention Claude Code.

- **Merging:** the owner merges, except the bot and docs classes in the workspace `CLAUDE.md` (Git), which the coordinator merges.

## What this is

Blog authoring studio (editor, AI writing agent, audio generation) behind Easy Auth, plus the internal-only blog read API. Posts, media and audio live in private Azure storage, never in this repo. No application code yet: the system spec is `../docs/shared/specs/2026-11-08-blog-studio.md` (workspace root, once approved). Overview: `README.md`.

## Commands

None yet. CI runs `workflow-lint` (actionlint) on PRs and pushes to `main`. Add the stack's test and lint commands here with the first code PR.

## Gotchas

- Public repo: never commit post content, media, audio, keys or `.env` files. `.gitignore` carries the baseline.
- The read API is not public. Nothing client-specific (Portfolio or otherwise) belongs in this repo.

## AI PR review

`.github/workflows/claude-review.yml` reviews each PR once it is ready, on later pushes, and when the owner comments `@claude`. Secret: `CLAUDE_CODE_OAUTH_TOKEN` (repo secret; expires about 2027-11). Fallback if subscription auth is refused: use `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}` in both jobs. Fork and Dependabot PRs are skipped. Do not require the `Claude Review` job as a status check: it skips on PRs that change the workflow file.

The `main` ruleset (`main-protect`) blocks deletion and force-push and requires a PR with 0 approvals; it requires the `workflow-lint` check.
