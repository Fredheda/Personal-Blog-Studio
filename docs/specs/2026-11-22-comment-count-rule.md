# The `comment-count` rule

- **Ticket:** BLOG-60 (phase B3 of the multi-agent SDLC; owner decision 572: "have some flexibility for discretion ... overall comment count should be reduced significantly"). Design source: the workspace spec `docs/shared/specs/2026-11-22-multi-agent-sdlc.md`, section 3.
- **Status:** done (PR #71). Plan: `docs/plans/2026-11-22-comment-count-rule.md`. Extends the `rules` job of BLOG-59 (merged, PR #69).

## Intent

The shared rules say comments are rare and cut when a file is edited. Prose does not stop a comment from growing back, so a fourth rule in `scripts/rules/` counts them: a PR may leave a file with fewer comment lines, never more, unless the PR description gives a reason for that file.

## Goals

- Rule `comment-count` runs in `scripts/rules/run.sh` after the other three rules, in CI job `rules` and in `scripts/ci-local.sh`.
- For every changed countable file, the comment lines after the PR must not exceed the count at the merge-base. A new file starts at zero. A renamed file is compared with its old path.
- Floor (owner decision 605 A): a changed countable file may hold at most one comment line per 40 code lines, and at least 2 are always allowed. Code lines are the non-blank lines that are not comment lines. A file above its allowance fails even when it shrank. The floor is its own small function (`over_floor`), next to the growth check (`growth`).
- A line `Comments: <path>: <reason>` in the PR description lifts the failure, growth or floor, for the file `<path>` only; a flagged file passes only when its own path is named, and the reason has at least one non-blank character.
- The CI job summary shows, per changed file and in total, the lines before, after and the change in percent, so the working standard (at least 70 percent fewer comment lines in touched files) is visible in every PR.
- Every behaviour has a violating test input written and run red before the code.

## Non-goals and anti-goals

- No cleanup of existing comments: that is the audit tickets (A*). This PR only stops growth and shows the change.
- No new dependency: Python standard library and `git`; the description is read with the `gh` CLI that CI runners carry.
- The rule is never loosened to pass: the only escape is the per-file `Comments:` line.

## What counts

| Language | Files | A comment line is |
|---|---|---|
| Python | `.py` | a physical line that carries a `#` comment, or a line of a docstring (the first statement of a module, class or function when it is a string) |
| TypeScript and JavaScript | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` | a physical line that carries a `//` comment or a line of a `/* */` or JSDoc comment (a JSX `{/* */}` is one) |
| Shell, YAML, TOML, Dockerfile | `.sh`, `.yml`, `.yaml`, `.toml`, `Dockerfile*` | a line whose first non-blank character is `#` |

The unit is the physical line, so a long block or docstring costs what it takes up. Strings, template literals and regular expressions are skipped by the code tokenizers, so `"https://x"` and `"# not"` are not comments.

Not counted: comments a tool needs, matched by the regular expressions in `scripts/rules/comment-directives.txt` (one `<language>`, tab, `<regex>` per line). Each pattern is anchored to the start of the comment text (after the comment marker and spaces), so `# ruff: noqa` is not counted and `# ruff is strict here` is. The directives: shebang, encoding line, `noqa`, `type: ignore`, `pyright:`, `ruff:`, `isort:`, `pylint:`, `mypy:`, `pragma:`, `nosec`, `fmt: off|on|skip`, `eslint-disable|enable`, `@ts-expect-error|ignore|nocheck|check`, `prettier-ignore`, `istanbul|v8|c8 ignore`, `/// <reference`, `@vitest-environment`, `@jest-environment`, `sourceMappingURL`, `shellcheck disable=`, `syntax=`, `escape=`, `check=`, `yaml-language-server`. The list is data so the scripts stay byte-identical across repos.

Not read: files in a directory named `fixtures` (as `pr-size`), the files listed in `scripts/rules/pr-size-generated.txt` (a regenerated file must not fail the rule), deleted files. A code file the tokenizer cannot read (invalid syntax) fails the rule and no `Comments:` line lifts that failure.

## Rule

| Input | Fails when |
|---|---|
| `git diff --name-status -M <merge-base> HEAD`, then the file text at the merge-base and at `HEAD` | a countable file has more comment lines after than before, or more than its allowance, and the description has no `Comments: <path>: <reason>` line for it; or a countable code file cannot be read |

Output: one verdict line (`comment-count: ok (<before> -> <after>)`, `comment-count: ok (<n> file(s) with a reason)` or `comment-count: FAIL ...`), then one indented line per file `  path: before -> after`, with `(reason given)` after a file a line lifted. The reason text is never printed: the description is untrusted text. When `GITHUB_STEP_SUMMARY` is set, a Markdown table (file, before, after, change in percent, allowance, and a total row) is appended to it; a file that starts with no comments and gains some shows `new`.

## Where the reasons come from

- Locally: the variable `COMMENTS_REASON`, which holds the same lines as the description.
- In CI: the pull request description, read through `gh api repos/<repo>/pulls/<n>` at run time, so editing the description and re-running the job works (a re-run replays the original event payload, which would hold the old description). The job already has `pull-requests: read`. A failed API call counts as no reason.
- A line is `Comments: <path>: <reason>` at the start of a line, one per file.

## Constraints

- Untrusted values (PR number, repository) reach scripts through `env`, never through the shell line; the description is read inside the script and never echoed.
- The `rules` job runs on the repo's Python (`setup-python` with `backend/.python-version`), so syntax newer than the runner's system Python is read as it is in the tests.
- The `rules` job id is unchanged, so `backend/tests/test_ci_parity.py` needs no change.
- Both sides of a comparison use the same counter, so a file's count is only compared with its own earlier count.
- Adding a rule changes no ruleset: `rules` becoming a required check stays the owner's step.

## Left to the builder

Helper names inside the modules, the wording of the failure line.

## Owner decisions this rests on

572 (discretion with a visible reduction), 573 (the owner reviews every PR), 574 (specs and plans in the repo). Specialist review of this spec: six edits (per-file reasons, percent summary and a separate growth check, anchored directives, hash comments in scripts and configuration, generated files skipped, a one-off cross-check of the TypeScript counter against the compiler's scanner). My calls, for the reviewer to check: the unit is the physical line, docstrings count, `fixtures` are excluded, the description is read through the API, an unreadable file always fails.
