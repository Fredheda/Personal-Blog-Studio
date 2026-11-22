# Details typed in place: title, summary, slug and tags in the page

- **Ticket:** BLOG-39. Parent design: studio design spec sections 7.4 and 10 (approved 2026-11-15, BLOG-32; workspace `docs/Personal-Blog-Studio/specs/2026-11-15-studio-design.md`). The behaviour that matters is restated below, so this spec stands alone.
- **Status:** proposed. Plan: `docs/plans/2026-11-22-details-in-place.md`.

## Intent

The post page is the post. Today a form of four labelled fields sits above the editor and a plain `h1` repeats the saved title. After this change the title is the page's `h1` typed in place, the summary sits under it, and the slug and tags are one row of pills. Nothing about saving changes: details still save only through Save, the text still autosaves, and Publish still waits for saved edits.

## Goals

- Title: the page's `h1`, an input named "Title", at most 200 characters, placeholder "Title".
- Summary: a textarea named "Summary" under the title in `muted` at 18.5px, at most 500 characters, placeholder "Add a summary: one or two sentences for lists and previews".
- Slug pill: shows `/slug`. A click turns it into an input named "Slug" that takes lower-case letters, digits and hyphens (other characters are dropped, spaces become hyphens, at most 100 characters, the server's limit); Enter, Escape or leaving the input closes it. Empty shows a dashed "Add a slug". Once the post has ever been published (`slugLocked`) the pill is read-only with a lock icon and the title "The slug is fixed once the post has been published".
- Tag pills: each tag is a pill with a remove button named "Remove tag <tag>"; a dashed "Add a tag" pill becomes an input named "Tags". Enter or a comma adds, Backspace in the empty input removes the last tag, leaving the input adds what was typed. A tag that is already there (any case) is not added twice. Tags stay optional.
- The row of pills closes with a divider and wraps on a phone; nothing makes the page wider than the screen.
- While Preview is on, the details show as plain text with no control: the title as `h1`, the summary, the slug and the tags as pills without buttons.
- The old form, its labels and the repeated saved-title `h1` are gone.
- One browser test per flow: typing and saving the details, the locked slug, the Preview, the phone layout. Each behaviour has a failing test written and run red first.

## Non-goals

- No change to the studio API, the proxy, the save logic, the ETags or the autosave.
- No tag suggestions, no tag list across posts, no slug generated from the title.
- No filter on what a tag may contain: the server's tag rule still decides at Save and shows its refusal, as it did for the old field. Filtering tags like the slug is a follow-up if the owner wants it.
- No steps lane change and no drafts lane (BLOG-40).
- No effect hooks: the new component holds only local state, so it needs nothing from the effects folder planned in BLOG-61.

## Approaches considered

1. **`PostEditor` keeps the details state and passes it to a presentational `PostDetails` (chosen).** The save, unsaved-details, conflict and reload code already reads that state; it changes in two small ways (tags become a list; a slug and tag edit goes through the same `edited()` call). One new component of about 160 lines holds only what is local to a control: whether the slug is being edited, whether a tag is being added, and the typed tag text.
2. `PostDetails` owns the state and reports it up. Rejected: the save and conflict code would need a second source of truth or a ref into the component, and `PostEditor` is already large.
3. Keep the form and restyle it. Rejected: the design asks for the details typed in the page.

## Constraints

- Existing accessible names stay: "Title", "Slug", "Summary", "Tags", "Save", "Publish", "Preview".
- Tags travel as a list: `PostEditor` holds `string[]`, `patchMeta` still sends `tags: string[]`, and "unsaved details" compares the lists.
- Typed text never leaves the page without Save: `edited()` runs on every details change as before.
- `PostEditor.tsx` is edited by BLOG-61 and BLOG-40; the three never run in parallel (this ticket goes first).
- Files this PR touches follow the comment standard: the floor and the content rule apply, so a separate cleanup commit cuts the comments in `PostEditor.tsx` that restate the code.
- No new dependency, no workflow change, no new Azure resource, no font or `url()` (hardening tests).

## Owner decisions this rests on

The design in 7.4 (approved 2026-11-15). My calls, for the reviewer to check:

- Tags typed in the pill input are added to the existing tags, where the old field replaced the whole text; duplicates are dropped ignoring case, the first spelling stays.
- The slug input filters what is typed (lower-case, spaces to hyphens, other characters dropped) instead of refusing at Save; the server's rule still decides at Save.
- Leaving the tag input adds the typed text, so nothing typed is lost.
- Preview shows "(untitled)" for an empty title, as the old heading did.

## Left to the builder

Tailwind classes of the pills, the lock icon's drawing, and the exact wording of the "Remove tag" button's visible mark.
