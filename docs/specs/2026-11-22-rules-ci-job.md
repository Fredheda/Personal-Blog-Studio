# The `rules` CI job: pr-size, spec-location, shared-block

- **Ticket:** BLOG-59 (phase B2 of the multi-agent SDLC; owner decisions 569 to 576). Design source: the workspace spec `docs/shared/specs/2026-11-22-multi-agent-sdlc.md`, section 4.
- **Status:** done (PR #69). Plan: `docs/plans/2026-11-22-rules-ci-job.md`.

## Intent

Every agent (Claude, Devin, later ones) goes through CI, so CI is the one place that binds all of them. Three small scripts check what the shared rules say in prose, so the prose can shrink. This repo builds the first version; the other repos copy it.

## Goals

- `scripts/rules/run.sh` runs every rule, prints one line per rule, exits non-zero on a violation.
- Rule `pr-size`: more than 25 changed files or 5000 changed lines fails.
- Rule `spec-location`: a PR that adds a spec or plan outside `docs/specs/` and `docs/plans/` fails.
- Rule `shared-block`: the block between `<!-- shared:start -->` and `<!-- shared:end -->` in `AGENTS.md` equals the owner's template, compared by hash.
- Each rule has a violating test input written and run red before the rule exists.
- A CI job `rules` and a step in `scripts/ci-local.sh` run `run.sh`.

## Non-goals and anti-goals

- `comment-count` is BLOG-60.
- No check that a ticket-named plan exists on `main`, and no check of plan and spec slugs: not in the ticket.
- No rule may be bypassed by an agent. In particular `size-override` counts only when the GitHub API says the repo owner's login set it: any account with write access can set a label, agents included.
- No new dependency: Python standard library and `git`; the label check uses the `gh` CLI that CI runners carry.

## Rules

| Rule | Input | Fails when |
|---|---|---|
| `pr-size` | `git diff --numstat -M <merge-base> HEAD` | files or lines above the limit after exclusions, and no owner-set `size-override` |
| `spec-location` | added and renamed-to paths of the same diff | a dated `.md` or `.mmd` file (`YYYY-MM-DD-slug`) or any `.md` under a directory named `spec`, `specs`, `plan`, `plans`, `superpowers` lies outside `docs/specs/` and `docs/plans/` |
| `shared-block` | `AGENTS.md` and `scripts/rules/shared-block.sha256` | the markers are missing or the block's sha256 differs from the recorded one |

`pr-size` exclusions: `package-lock.json`, `poetry.lock`; any file in a directory named `fixtures`; anything under `docs/`; the paths in `scripts/rules/pr-size-generated.txt`. Lines are added plus deleted. A binary file counts as a file and as zero lines. A rename counts once, at its new path.

`size-override`: in CI the rule reads the label events of the PR from the GitHub API and accepts the label only when the latest `labeled` or `unlabeled` event for it is a `labeled` by the repository owner. A failed API call counts as no override. Locally the label cannot be checked, so the limit applies. Setting the label does not re-run the job (`labeled` is not a trigger of `ci.yml`, and stays out): the owner sets it and re-runs the job; the failure line says so.

The `pr-size` generated-files list is data, not code: `scripts/rules/pr-size-generated.txt`, one path per line (`openapi/v1.json`, `frontend/next-env.d.ts`), so the scripts stay byte-identical across repos and only the data file differs.

`shared-block` hash: sha256 of the block text from the start marker line to the end marker line, inclusive, lines joined with `\n` and one trailing `\n`. `scripts/rules/shared_block.py --print-hash <file>` prints it; the recorded hash is the hash of the owner's template file `agents-shared-block.md`. When the owner changes the template, the hash file changes with the matching `AGENTS.md` block in one PR. When a PR's diff touches the hash file the rule still compares block and hash, and on success prints `shared-block: ok (hash file changed in this PR)`, so a block and its hash cannot change together unseen.

## Where the rules read the base

`BASE_SHA` (CI: the PR's base commit), default `origin/main`. The diff runs from the merge-base, so a PR that is behind `main` is not blamed for `main`'s changes.

## Constraints

- The `rules` job has no `if` and no `needs`: it runs on drafts and on docs-only PRs too.
- The CI job needs the full history (`fetch-depth: 0`) for the merge-base and the permissions `contents`, `pull-requests` and `issues` read.
- Untrusted event values reach scripts through `env`, never through the shell line.
- The `rules` job id must appear as `step "rules"` in `scripts/ci-local.sh` (`backend/tests/test_ci_parity.py`).
- Adding `rules` to the `main` ruleset's required checks is the owner's step after the job has run once on `main`; this work changes no ruleset.

## Left to the builder

File layout inside `scripts/rules/`, helper names, the exact wording of failure lines.

## Owner decisions this rests on

569 to 576: shared block copied per repo (570), size limit 25 files and 5000 lines with an owner-only override (573), specs and plans in the repo and a docs PR before the code PR (574).
