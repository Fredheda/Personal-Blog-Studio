# The `comment-count` rule

- **Ticket:** BLOG-60 (phase B3 of the multi-agent SDLC; owner decision 572: "have some flexibility for discretion ... overall comment count should be reduced significantly"). Design source: the workspace spec `docs/shared/specs/2026-11-22-multi-agent-sdlc.md`, section 3.
- **Status:** proposed. Plan: `docs/plans/2026-11-22-comment-count-rule.md`. Extends the `rules` job of BLOG-59 (merged, PR #69).

## Intent

The shared rules say comments are rare and cut when a file is edited. Prose does not stop a comment from growing back, so a fourth rule in `scripts/rules/` counts them: a PR may leave a file with fewer comments, never more, unless its description gives a reason.

## Goals

- Rule `comment-count` runs in `scripts/rules/run.sh` after the other three rules, in CI job `rules` and in `scripts/ci-local.sh`.
- For every changed code file, the comment count after the PR must not exceed the count at the merge-base. A new file starts at zero. A renamed file is compared with its old path.
- A line `Comments: <reason>` in the PR description lifts the failure. A reason is at least one non-blank character.
- The CI job summary shows the count before and after for every changed file and the total, so the overall reduction is visible.
- Every behaviour has a violating test input written and run red before the code.

## Non-goals and anti-goals

- No cleanup of existing comments: that is the audit tickets (A*). This PR only stops growth.
- No new dependency: Python standard library and `git`; the description is read with the `gh` CLI that CI runners carry.
- The rule is never loosened to pass: the only escape is the `Comments:` line.

## What counts

| Language | Files | A comment line is |
|---|---|---|
| Python | `.py` | a physical line that carries a `#` comment, or a line of a docstring (the first statement of a module, class or function when it is a string) |
| TypeScript and JavaScript | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` | a physical line that carries a `//` comment or a line of a `/* */` comment (a JSX `{/* */}` is one) |

The unit is the physical line, so a long block or docstring costs what it takes up and cannot be used to get around a limit on single-line comments. Strings, template literals and regular expressions are skipped by the tokenizers, so `"https://x"` and `"# not"` are not comments.

Not counted: comments that tool configuration needs, matched by the regular expressions in `scripts/rules/comment-directives.txt` (one `<language>`, tab, `<regex>` per line): shebang, encoding line, `noqa`, `type: ignore`, `pyright`, `ruff`, `isort`, `pylint`, `pragma`, `nosec`, `fmt: off|on|skip`, `eslint-disable|enable`, `@ts-expect-error|ignore|nocheck|check`, `prettier-ignore`, `istanbul|v8|c8 ignore`, `/// <reference`, `@vitest-environment`, `@jest-environment`, `sourceMappingURL`. The list is data so the scripts stay byte-identical across repos.

Files in a directory named `fixtures` are not counted (the same exclusion `pr-size` uses). Deleted files are not read. A file the tokenizer cannot read (invalid syntax) fails the rule and the `Comments:` line does not lift that failure.

## Rule

| Input | Fails when |
|---|---|
| `git diff --name-status -M <merge-base> HEAD`, then the file text at the merge-base and at `HEAD` | any counted file has more comment lines after than before, and the description has no `Comments:` line; or a counted file cannot be read |

Output: one verdict line (`comment-count: ok (<before> -> <after>)`, `comment-count: ok (Comments: <reason>)` or `comment-count: FAIL ...`), then one indented line per file `  path: before -> after`. When `GITHUB_STEP_SUMMARY` is set, a Markdown table with the same numbers and a total row is appended to it.

## Where the reason comes from

- Locally: the variable `COMMENTS_REASON` (the whole value is the reason).
- In CI: the pull request description, read through `gh api repos/<repo>/pulls/<n>` at run time, so editing the description and re-running the job works (a re-run replays the original event payload, which would hold the old description). The job already has `pull-requests: read`. A failed API call counts as no reason.
- The line format is `Comments: <reason>` at the start of a line; the first matching line wins.

## Constraints

- Untrusted values (PR number, repository) reach scripts through `env`, never through the shell line; the description is read inside the script.
- The `rules` job id is unchanged, so `backend/tests/test_ci_parity.py` needs no change.
- Both sides of a comparison use the same tokenizer, so a file's count is only compared with its own earlier count.
- Adding a rule changes no ruleset: `rules` becoming a required check stays the owner's step.

## Left to the builder

Helper names inside the modules, the wording of the failure line.

## Owner decisions this rests on

572 (discretion with a visible reduction), 573 (the owner reviews every PR), 574 (specs and plans in the repo). My calls, for the reviewer to check: the unit is the physical line, docstrings count, `fixtures` are excluded, the description is read through the API, an unreadable file always fails.
