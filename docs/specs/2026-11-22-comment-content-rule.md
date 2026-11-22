# The `comment-content` rule and the comment lint settings

- **Ticket:** BLOG-62 (owner decisions 606: three layers with no new dependency, 607: no escape for the content rule). Layer 3, `comment-count`, is `docs/specs/2026-11-22-comment-count-rule.md`.
- **Status:** proposed. Plan: `docs/plans/2026-11-22-comment-content-rule.md`.

## Intent

The amount of comments is bounded by `comment-count`. What is left must also be the right kind: no pointer to a ticket or a plan, no history, no narration of the file at the top, no docstring that repeats the signature. Ready-made lint rules cover commented-out code and marker comments; one rule of our own covers the rest. Both run in the existing `rules` job and in `scripts/ci-local.sh`, so every agent is bound the same way.

## Goals

- Layer 1, lint settings. Ruff `ERA001` (commented-out code) and `FIX001` to `FIX004` (FIXME, TODO, XXX, HACK) in the backend; ESLint core `no-warning-comments` (terms todo, fixme, xxx, hack, anywhere in a comment) in the frontend. Configuration only, no new dependency. Each setting has a test that feeds it a violating input.
- Layer 2, rule `comment-content` in `scripts/rules/`, run by `run.sh` after `comment-count`. For every file a PR adds, changes or renames (the same set and the same exclusions as `comment-count`), a comment fails when it:
  - names a ticket (`BLOG-12`, `PAIR-3` and the other project keys);
  - points at a spec or a plan (`docs/specs/`, `docs/plans/`, `superpowers`);
  - names another project of the workspace (names in `scripts/rules/comment-projects.txt`);
  - narrates history (used to, no longer, git history, removed in, previously, formerly, before or after this change, this PR, this ticket);
  - sits in a file header longer than 3 comment lines (the comment lines, a module docstring included, before the first line of code; shebang and tool directives are skipped);
  - is a Python docstring whose words, leaving out filler words, are all words of the function or class name and its parameter names.
- A guard in the same rule: a tool directive that switches off every lint rule on its line (`noqa` without a code, `ruff: noqa`, `eslint-disable` without a rule name) or that names `ERA`, `FIX` or `no-warning-comments` fails.
- Patterns are data, not code: `scripts/rules/comment-content-patterns.txt` (`kind`, language, regex and the message, tab separated) and `scripts/rules/comment-projects.txt`. Changing one is a visible diff in a PR the owner reviews. The scripts stay byte-identical across repos; the data files carry the same lists.
- Each behaviour has a violating test input written and run red before the code.

## No escape

The `Comments:` line of `comment-count` does not lift any of these failures (owner decision 607). A failure is removed by deleting or rewording the comment.

## Output

`comment-content: ok (<n> file(s) read)` or `comment-content: FAIL <n> problem(s)` followed by one line per problem, `  <path>:<line>: <what to delete>`. The message comes from the data file or from the rule; the text of the comment is never printed. A file the tokenizer cannot read fails with `  <path>: cannot read comments`.

## Design

- The three tokenizers of `comment-count` return the comments themselves instead of only a count: a `Comment` holds the first and last line, the text, whether it is a tool directive and, for a docstring, the words of the owner's name and parameters. `count` stays the number of lines of the comments that are not directives, so `comment-count` behaves as before.
- Directive comments are kept in the list, flagged, so the guard sees them and the header check can skip them.
- Content patterns apply to comments that are not directives; guard patterns apply to directives. A pattern has a language (`all`, `python`, `ts`, `hash`).
- Project names are matched as whole words, ignoring case.

## Constraints

- No new dependency: standard library and `git`. Ruff and ESLint are already locked in the repo.
- No repo file states how a rule can be avoided; failure messages say what to delete.
- Existing files that break the rule are cleaned in the audit tickets; the rule reads only the files a PR touches.
- The `rules` job and `scripts/ci-local.sh` already run `run.sh`: no workflow change.

## Left to the builder

Helper names, the exact list of filler words, the exact wording of messages.

## Owner decisions this rests on

606 (three layers, no new dependency), 605 (floor, in `comment-count`), 607 (no escape). My calls, for the reviewer to check: the header limit counts a module docstring; a docstring counts as repeating only when every non-filler word is a word of the name or parameters; the guard looks at directives of touched files only.
