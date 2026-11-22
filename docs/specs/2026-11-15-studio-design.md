# Studio design: pipeline page with a drafts lane

Copied into the repo 2026-11-22 so cloud agents can read it.

- **Status:** approved by the owner, 2026-11-15 (BLOG-32 comment 11306), browser tests included. The mockup was approved before (comment 11261). Builder check done (2026-11-15): edit time added to section 8, ticket order changed so each PR deploys alone.
- **Date:** 2026-11-15
- **Repo:** `Personal-Blog-Studio`. **Ticket:** BLOG-32 (holding ticket, Done; replaced by the build tickets BLOG-35 to BLOG-42, section 10).
- **Approved mockup:** `c-screens-round3.html` (workspace file in the mockup folder for 2026-11-14-studio-design; not in the repo). Open it in a browser: keys 1 to 4 switch screens, A shows or hides the agent panel. Earlier rounds, same folder: `editor-directions-round1.html`, `c-switching-round2.html`.
- **Builds on:** the system spec `2026-11-08-blog-studio.md` (section 7, workspace, not in the repo), the editor plan `2026-11-14-blog-studio-editor.md` (BLOG-30, revision 3, workspace, not in the repo), the studio shell (PR #30, merged).
- **Skills applied:** `superpowers:brainstorming` with the visual companion, `frontend-design`.

Where this document and the mockup disagree, this document wins. Where it is silent, the mockup is the reference for look, spacing and wording.

## 1. TL;DR

- The studio gets one look and one layout: a dark graphite page that reads like the published post, a left lane with all drafts above three steps (Write, Check, Publish), and a place held for the writing agent on the right.
- New behaviour: switch between drafts from the lane; the post is checked after every save, so the lane always says whether it would publish; an All posts page to manage everything (filter, unpublish, delete a draft).
- Eight PRs, one ticket each (section 10), after BLOG-30; the API ticket may run beside it. The first sets up browser tests. One holds the backend additions: published status, a true edit time and a check endpoint in the studio API.
- Styling uses Tailwind CSS (owner decision). One new frontend dependency; no fonts.
- Owner actions: review and merge each PR; the Deploy button after merges. No Azure change, no new secret.
- Cost: none.

## 2. Intent

The owner writes long technical posts (maths, code) and manages drafts and published posts, alone, mostly on a laptop. The studio works but "looks too bare". He wants it to feel like "a modern, cool, and AI enabled blog writing and content management studio". Both halves count: writing and managing.

## 3. Owner decisions

From the specialist's chat unless marked, recorded on BLOG-32.

| Decision | His words | Comment |
|---|---|---|
| Feel | "a modern, cool, and AI enabled blog writing and content management studio" | 11214 |
| Direction C, the pipeline page | "I like C the best, but it needs a way to work on multiple drafts at the same time / switch between them" | 11255 |
| Drafts in the left lane, one post open at a time | "option 2" | 11258 |
| Check after every save; rest of the mockup approved | "option A, rest looks good" | 11261 |
| Tailwind CSS | "not plain CSS. It should be using tailwind please" | 11264 |
| This document and the ticket list approved; browser tests yes | "spec should be fine, lets do browser tests" (relayed by the coordinator) | 11306 |

Fixed earlier (not reopened): system font stacks only, maths as MathML, no remote images, Milkdown Crepe as the editor, one Save button, only the body autosaves, tags optional, Publish only when nothing is unsaved.

## 4. Goals, non-goals, anti-goals

**Goals.** A distinct, modern look. Writing in a page that looks like the result. Drafts one click apart. Always-visible answer to "would this publish?". A real management view. A design the agent (BLOG-11) drops into without a second redesign.

**Non-goals.** Tabs or side-by-side editing (shown, not chosen). A light theme (dark only, `color-scheme: dark`). Building the agent panel, uploads, media blocks, cover images or revisions UI (their own tickets; section 11). Slug suggestions from the title. Sorting options in All posts.

**Anti-goals.** Any font file or web font. A control that does nothing yet (no agent button, no "ask" wording before the agent ships). Colour used as decoration: the iridescent gradient marks the brand dot and agent parts only. Losing typed text or unsaved details silently on a switch.

## 5. Constraints

- Fonts: system stacks only; no `@font-face`, `next/font`, font file or font CDN (`frontend/tests/hardening.test.ts`, the build's font gate from BLOG-30). Maths: MathML only, KaTeX CSS never imported.
- The web app sends `Content-Security-Policy: img-src 'self' data: blob:; media-src 'self'` (BLOG-30). No remote image anywhere in the UI; icons are inline SVG.
- The editor is Milkdown Crepe: themed, not replaced, client-only through `next/dynamic`.
- BLOG-30 behaviour stays: body autosave (one loop, stops on a 412, no timer retry), `saveAll()` for Save, Publish disabled while anything is unsaved, the editor reports no change on load, the leave guard.
- Next.js 16 and React 19: read the guides under `frontend/node_modules/next/dist/docs/` first. Tailwind and Crepe: check current docs (Context7) at plan time.
- Dependencies pinned exactly; npm 12 blocks install scripts unless approved (`CLAUDE.md`, Gotchas).

## 6. Approaches considered

**Look and layout (round 1).** A "Lamp-lit page": dark desk, one bright serif page, floating panels, agent bar at the bottom. B "Night workbench": three docked panes, spruce green with saffron. C "Pipeline page": the page reads like the published post, details typed in place, a lane walking Write, Check, Publish, graphite with colour only on agent parts. The owner chose C.

**Working on several drafts (round 2).** 1 Tabs: each open post keeps its state; medium build. 2 Drafts in the left lane: all drafts listed, one post open, a switch saves the text and asks about unsaved details; small build. 3 Side by side: two posts at once; large build, costs the lane and the agent panel. The specialist recommended 1; the owner chose 2.

**Check step.** A: check after every save through a small new endpoint; Publish off while problems are listed. B: no backend change; problems appear only after a refused publish. The owner chose A.

**Styling.** Hand-written CSS with tokens (no dependency), Tailwind CSS, or a component library (brings its own look to override). The specialist picked hand-written CSS; the owner chose Tailwind.

## 7. The design

### 7.1 Tokens

Defined once as the Tailwind theme (`@theme` in `app/globals.css`), so utilities such as `bg-pane` and `text-muted` exist. Keep `--ui-font` and `--ui-mono` defined (BLOG-30 and the hardening tests use them) and point Tailwind's `--font-sans` and `--font-mono` at them.

| Token | Value | Use |
|---|---|---|
| `bg` | `#101217` | page background |
| `deep` | `#0b0d11` | lane, code blocks, phone bars |
| `pane` | `#181b22` | panels, active lane row, dialog, pills |
| `raise` | `#20242d` | raised controls, hover |
| `line` | `#2a2f3b` | borders and dividers (decorative) |
| `text` | `#f1f3f7` | headings, UI text |
| `ink` | `#dfe3ea` | post body text |
| `muted` | `#98a1b3` | secondary text |
| `ok` | `#5fe3a1` | saved, passed, published; text on it `#06281a` |
| `warn` | `#ffb454` | unsaved details, problems, conflict |
| `err` | `#ff7b7b` | failed save |
| primary button | `#ffffff` on it `#101217` | Publish, New post, dialog default |
| `iri` | `linear-gradient(100deg,#5ee7ff 0%,#8b7bff 42%,#ff7ad9 78%,#ffc46b 100%)` | brand dot, agent parts only |
| code | ink `#e6e9f0`, keyword `#b9a8ff`, function `#7fe0ff`, number `#ffc46b`, comment `#7c879a` | code blocks on `deep` |

Contrast, computed (WCAG): `text` on `bg` 16.9, on `pane` 15.5, on `raise` 14.0; `ink` on `bg` 14.6; `muted` on `bg` 7.2, on `deep` 7.5, on `pane` 6.6, on `raise` 6.0; `ok` on `bg` 11.6; `warn` on `bg` 10.6; `err` on `bg` 7.5; code comment on `deep` 5.4 (the mockup's `#6f7a8d` is 4.49 and is replaced). A unit test computes these pairs from the theme and fails under 4.5, so a token edit cannot regress them. `line` is decorative (1.4) and never the only sign of a control: focus is `outline: 2px solid #fff; outline-offset: 2px` on `:focus-visible`.

**Type.** UI 14px/1.45. Sizes: 12.5 (meta), 13.5 (lane rows, chips), 14.5 (step names), 16.5/1.65 (post body, measure at most 66 characters), 18.5/1.45 (summary), 1.32em (h2 in the body), 30 (All posts heading), 40/1.08 with letter-spacing -0.028em (post title). Weights 500, 600, 650, 720 (system fonts round to the nearest they have). Sentence case everywhere; no all-caps labels; monospace only for code.

**Shape.** Radius 8 (small buttons), 10 (buttons, inputs, lane rows), 12 (message strip), 16 (dialog), 20 (agent panel), full (pills, status dots). No decorative shadows; shadow only under the dialog and sheets. No motion is required; any transition respects `prefers-reduced-motion`.

**Tailwind notes.** Preflight removes the browser's heading, list and table styles: the Preview (`components/Preview.tsx`) and anything else that relied on them need the body rules above as one shared class, written once and used by the Preview so it matches the editor. No typography plugin. Crepe is themed through its CSS variables in `globals.css` (7.4); that is the one place hand-written CSS remains.

### 7.2 Layout

Three columns under a top bar: lane, page, agent slot.

| Width | Lane | Page | Agent slot |
|---|---|---|---|
| 1180px and up | 262px, `deep`, right border | fills; content column at most 720px, 40px top padding | 380px when the agent exists and is open; otherwise absent and the content column is centred |
| 760 to 1179px | 232px | fills | overlays as a drawer (agent ticket) |
| under 760px | hidden (7.9) | full width, 18px side padding | full screen (agent ticket) |

The lane and the steps show on a post page (`/posts/[id]`) only. All posts (`/`) has the top bar and no lane.

### 7.3 Top bar

58px, bottom border. Left: brand (iridescent dot + "Studio", links to `/`), "All posts" (links to `/`, highlighted there). Centre: the quick-open field (ticket 7; absent until then). Right, on a post page only: save state, Preview, Save, Publish.

**Save state** (dot + text, first match wins):

| # | When | Dot | Text |
|---|---|---|---|
| 1 | a 412 on the body or the details | red | Not saved: the post changed elsewhere |
| 2 | the last body save failed | red | Not saved |
| 3 | a save is running | grey | Saving… |
| 4 | details differ from the saved ones | amber | Unsaved details |
| 5 | typed text waits for autosave | amber | Unsaved changes |
| 6 | otherwise | green | Saved, then a relative time ("just now", "2 min ago"); on open it counts from the post's `updatedAt` (section 8, edit time) |

**Buttons.**
- **Preview** toggles (`aria-pressed`) between the editor and the rendered Preview in the same place; details show as plain text while it is on.
- **Save** is enabled in states 2, 4 and 5 and gets a white border then; otherwise dimmed with the title "Nothing to save". It calls `saveAll()`.
- **Publish** (white) is enabled only in state 6 and when the check is not running and lists no problems. Dimmed otherwise, with the title "Save your edits first", "Fix the problems under Check first" or "Checking…". If the check itself failed (7.5), Publish stays enabled: the server validates again and a refusal fills the Check step.

### 7.4 Page

The page is the post. No form above the editor.

- **Title:** the page's `h1`, typed in place (accessible name "Title", at most 200 characters, placeholder "Title").
- **Summary:** under the title in `muted` at 18.5px (name "Summary", at most 500, placeholder "Add a summary: one or two sentences for lists and previews").
- **Slug and tags:** one row of pills under the summary, closed by a divider. The slug pill shows `/slug`; a click turns it into an input (name "Slug", lower-case letters, digits and hyphens); empty shows a dashed "Add a slug". Once the post has ever been published the pill is read-only with a lock icon and the title "The slug is fixed once the post has been published". Each tag is a pill with a remove button; the dashed "Add a tag" pill becomes an input (name "Tags"); Enter or a comma adds, Backspace in the empty input removes the last. Tags stay optional.
- **Body:** Crepe, no border, same column.

Details save only through Save. The text autosaves.

**Crepe theme.** Start from Crepe's dark base theme and override on `.crepe .milkdown` (selector and variable names per Milkdown's styling guide; verify against the installed version):

| Crepe variable | Value |
|---|---|
| `--crepe-color-background` | `bg` |
| `--crepe-color-on-background` | `ink` |
| `--crepe-color-surface`, `--crepe-color-surface-low` | `pane`, `deep` |
| `--crepe-color-on-surface`, `--crepe-color-on-surface-variant` | `text`, `muted` |
| `--crepe-color-primary` | `text` (no coloured accent) |
| `--crepe-color-secondary`, `--crepe-color-on-secondary` | `raise`, `text` |
| `--crepe-color-inverse`, `--crepe-color-on-inverse` | `text`, `bg` |
| `--crepe-color-outline` | `muted` (Crepe colours list bullets and numbers with it; the first value, `#3a4050`, had contrast 1.8 on `bg`; owner decision 497, 2026-11-21) |
| `--crepe-color-inline-code` | `#e6e9f0` |
| `--crepe-color-error` | `err` |
| `--crepe-color-hover`, `--crepe-color-selected`, `--crepe-color-inline-area` | `raise`, `#2f3542`, `raise` |
| `--crepe-font-title`, `--crepe-font-default`, `--crepe-font-code` | `--ui-font`, `--ui-font`, `--ui-mono` |
| `--crepe-base-font-size` | `16.5px` |

Code blocks sit on `deep` with the code colours of 7.1. The hardening test (no `@font-face`, no `url()` in Crepe's theme CSS) must pass for the dark theme file too.

### 7.5 Steps: Write, Check, Publish

A numbered vertical list in the lane, under the drafts (a real sequence). Each step has a round marker, a name and one line of status. Marker: green filled = done, white ring = in progress or next, amber ring = needs you, red ring = failed, grey ring = waiting.

**1 Write** follows the save state of 7.3:

| Save state | Marker | Text |
|---|---|---|
| 6 saved | green | Saved 2 min ago |
| 5 or 3 | white | Unsaved changes / Saving… |
| 4 | amber | Unsaved details. Press Save. |
| 2 | red | Not saved. Your next edit or Save tries again. |
| 1 | red | Not saved: the post changed elsewhere. |

**2 Check** shows the answer of the check endpoint (section 8) for what is saved. The check runs when the post opens and after every successful save of the body or the details; only the latest answer counts (an answer whose ETags are not the current ones is dropped).

| When | Marker | Text |
|---|---|---|
| Write is not in state 6 | grey | Waits for a save |
| request running | white | Checking… |
| no problems | green | No problems found |
| problems | amber | "1 thing to fix before publishing" or "n things to fix before publishing", then the list |
| the request failed | grey | Could not check. The next save tries again. |

Each problem is a small card: "Line n" in `warn` and the message; a problem without a line (line 0, such as a missing slug) shows the message only, first letter capitalised. A click on a problem with a line moves the cursor to that place in the editor (the block that holds the line; section 11 has the mapping rule and its guard).

**3 Publish.**

| When | Marker | Text |
|---|---|---|
| published | green | "Published, version n, on 9 Nov. Publish again to send your changes." and an "Unpublish" link |
| not published, something unsaved | grey | Off while something is unsaved |
| not published, problems listed | grey | Off until the list above is empty |
| not published, ready | white | "Not published yet. Goes live at /slug" |

Unpublish asks first (7.7). The Publish button itself stays in the top bar.

### 7.6 Drafts lane and switching

- Header "Drafts" with the count and a "+" button (name "New post"). Rows: title on one line (ellipsis; "(untitled)" when empty) and "Edited" plus a relative date. The open post's row is highlighted (`pane`, border). Newest edit first (the API's order).
- Below: a "Published" row with the count; it expands to the published posts in the same row format with a green dot. It opens by itself when the open post is published. A published post is listed there even when its draft has newer edits.
- The lists scroll inside the lane; the steps stay visible.
- The lane reloads after a create, a details save, a publish, an unpublish and a delete.
- **New post:** "+" puts a title input at the top of the list (placeholder "Title of the new post", hint "Enter creates the draft and opens it. Esc cancels."). Enter with a non-empty title creates the post and opens it; Esc or leaving the empty input cancels. A failure shows in the message strip.
- **Switching:** a click on a row, on "All posts", on the brand or on a quick-open result first flushes the text (`flush()`). If the text cannot be saved, nothing switches and the message strip says why. If the details are unsaved, the switch dialog (7.7) asks. Otherwise it navigates. Closing the tab keeps BLOG-30's leave guard.

### 7.7 Messages and dialogs

**One message strip** sits at the top of the page column. Validator problems never go there; they belong to Check.

| Kind | Look | Text | Role |
|---|---|---|---|
| Conflict (412) | amber border and tint, white button "Reload the post" | "This post changed elsewhere. Reload it to continue; your unsaved text stays on the page until then." | alert |
| Request failed | red border and tint | the API's title and detail, as `ProblemList` gives them today | alert |
| No answer or expired session | red | "Could not reach the studio. Your session may have expired: reload the page to sign in again." | alert |
| Publish refused although the check passed | amber | "Not published: fix the problems listed under Check." | alert |
| Published | green | "Published as version n. Live at /slug." | status |
| Unpublished | green | "Unpublished. /blog/<slug> can stay on the live site for a few seconds." (owner 560 A, keeping BLOG-43; "The post" when there is no slug) | status |

A green strip goes away with the next edit. While a conflict shows, Save and Publish stay off until the reload.

**Dialogs** (panel on `pane`, radius 16, default action white and on the right, Esc is the cautious action):

| Dialog | Title | Body | Buttons |
|---|---|---|---|
| Switch with unsaved details | Save the details before switching? | The title, summary or tags of "<title>" have changes that are not saved. The text itself is saved. | Stay here, Discard changes, **Save and switch** |
| Unpublish | Unpublish this post? | It leaves the blog at once. The draft and its published versions stay in the studio. | Keep it published, **Unpublish** |
| Delete a draft | Delete this draft? | "<title>" and its revisions are removed. You can get it back for 7 days by asking. | Keep it, **Delete draft** |
| Delete a post that was ever published | Delete this post? | "<title>" is taken off the blog and removed, with its published versions. You can get it back for 7 days by asking. | Keep it, **Delete post** |

"Save and switch" runs `saveAll()`; it switches only when that answers yes, otherwise it stays and the strip shows the reason.

### 7.8 All posts

The page at `/`. Heading "Posts", white "New post" button (adds a first table row with the same title input as the lane). A segmented filter "All n", "Drafts n", "Published n" and a "Filter by title" field (matches while typing, ignores case).

Table: Title (with `/slug` or "No slug yet" under it), Status (grey ring "Draft", or green dot "Published" and "version n"), Last edited, actions. A row click or "Open" opens the post. Every post has "Delete"; a published one also has "Unpublish". Both ask first (7.7). Delete of a post that was ever published uses the second delete dialog and sends `confirm=published`; a 404 answer counts as done (owner decision of 2026-11-17, workspace record `completed/2026-11-17-studio-delete-post.md`, not in the repo). Order: last edited, newest first.

Empty studio: "Nothing written yet", "Give the first post a title. The page, the checks and publishing follow from there.", a "New post" button. Filter without a match: "No post matches "<text>"."

### 7.9 Phone (under 760px)

Phone-safe, not phone-first: read, fix a typo, publish.

- Top bar: brand dot, the post title as a button with a chevron, Publish.
- A tap on the title opens a bottom sheet with the lane's lists, the "+" and an "All posts" link.
- The steps become a strip of three chips under the top bar ("1 Saved", "2 No problems" or "2 2 to fix", "3 Not published" or "3 Published"), coloured as their markers. A tap on the Check chip opens the problems as a sheet.
- Preview and Save move to a bottom bar.
- All posts: each row stacks to title, then status and date, then actions.

### 7.10 Agent panel (place held, not built here)

Until the agent ticket (BLOG-11) ships there is no panel, no agent button and no agent wording. The agent tickets build to this look: a panel on `pane` with radius 20 and a 1.5px iridescent border; header with the iridescent dot, "Writing agent" and the model as a pill; "Working on <title>"; source files as chips (uploads ticket); the chat; an edit card with a short iridescent bar on its left and "Keep" and "Undo"; suggestion chips; a composer whose send button is iridescent. Opening it moves the content column from centred to left-aligned. Screen 1 of the mockup with the panel on is the reference.

### 7.11 Wording rules

Sentence case. Buttons say what happens ("Save and switch", "Reload the post"). An action keeps its name everywhere ("Publish" then "Published"). Errors say what happened and what to do; no apology. Existing accessible names stay: "Title", "Slug", "Summary", "Tags", "Save", "Publish", "Preview".

## 8. Backend additions

Small, in `studio_api` (internal API; the read API contract `openapi/v1.json` is untouched). Shapes are proposals; the plan fixes them.

1. **Published status.** `GET /posts` items and `GET /posts/{id}` gain `published` (bool), `version` (number or null) and `publishedAt` (string or null); the single post also gains `slugLocked` (ever published). The list must not read one blob per post for this: read the published index once.
2. **Edit time.** Today `updatedAt` moves only on create and on a details save; a body save leaves it alone (`PostService.update_body`). The lane, All posts and "Saved 2 min ago" on open need the time of the last edit of either half, and the list sorted by it. `updatedAt` becomes the later of the two. Not by rewriting `draft.json` on each body save: that changes the details ETag and the next Save would get a 412. The plan picks the mechanism (for example the body blob's modified time through `BlobStore`, with the Azure store, the fake and the contract test changed together).
3. **Check.** `GET /posts/{id}/check` answers `{ ok, problems: [{ line, message }], bodyEtag, metaEtag }` for what is saved, with exactly the rules publish applies before it writes (title, slug and summary present, `validate_body`, slug not taken by another post). Publish and check share one function, and a test proves they agree on the editor fixtures. Read-only: nothing is written.
4. **Client.** `lib/studio-api.ts` gains the new fields, `checkPost(id)` and `deletePost(id)` (the route `DELETE /posts/{id}` exists).

## 9. Left to the builder

Component and file names; Tailwind class choices; whether dialogs use the native `<dialog>`; how relative times refresh; how a switch is intercepted (our own links call one guarded navigate function); how the lane's lists and the Published row remember being open; the CodeMirror theme mechanism inside Crepe (the colours of 7.1 are the requirement); breakpoint fine-tuning; debounce of the check; test layout. Each plan follows the workspace rules: tests first, full code, owner-runnable gates, docs updated.

## 10. Build tickets

One PR each, in this order, after BLOG-30 is merged (ticket 1 may run beside it). Sizes: S up to about 8 files, M about 10 to 20. Every UI ticket includes its phone layout (7.9) and its states. Tickets 3 to 7 each add one browser test per flow.

**Every PR leaves the studio complete and can be deployed alone:** no control is removed before its new home exists. That is why the steps lane (which takes over Unpublish and the publish problems) comes before the details move into the page.

| # | Title | Scope | Size | Needs |
|---|---|---|---|---|
| 0 (BLOG-35) | Browser tests for the studio | Playwright against the frontend with a stubbed studio API, one CI job, first test: open a post, type, see it saved. Per the repo standard (`setting-up-a-repo`; reference `copilot-kit-exp`). | M | BLOG-30 |
| 1 (BLOG-36) | Studio API: published status, edit time and a check endpoint | Section 8, backend and client. Tests: status fields from the index, edit time after a body save and the list order, check equals publish on the fixtures, delete call. | M | none (may run beside BLOG-30) |
| 2 (BLOG-37) | Studio theme with Tailwind | Tailwind setup, tokens as the theme (7.1), contrast test, top bar with brand and "All posts", buttons, pills, message strip and dialog components, shared body styles for the Preview, Crepe dark theme (7.4). The pages keep their current layout and controls, restyled. | M | BLOG-30 |
| 3 (BLOG-38) | Steps lane and top bar actions | 7.3, 7.5, 7.7: the lane column with Write, Check, Publish; save state, Preview, Save and Publish move to the top bar; the check after each save; Publish off on problems; Unpublish moves into the Publish step with its dialog; the message strip replaces the notices at the bottom. The details form stays above the editor for this PR. Phone strip, problems sheet and click-to-line are BLOG-54. | M | 0, 1, 2 |
| 4 (BLOG-39) | Details typed in place | 7.4: title, summary, slug pill (locked once published) and tag pills in the page; the form goes. | M | 3 |
| 5 (BLOG-40) | Drafts lane and switching | 7.6: lists, Published row, new post in the lane, guarded switch with its dialog, phone sheet. | M | 4 |
| 6 (BLOG-41) | All posts page | 7.8: table, filter, new post row, delete and unpublish with dialogs, empty states. | M | 0, 1, 2 |
| 7 (BLOG-42) | Quick open | The centre field and Cmd/Ctrl+K: find a post by title and open it (through the guarded switch), "New post". Placeholder "Open a post or run a command"; "ask" joins with the agent. | S | 5 |

Ticket 3 shipped as BLOG-38 (desktop: steps lane, top bar actions, check, strips) and BLOG-54 (phone chip strip, problems sheet, click-to-line spike). Tickets 3, 4 and 5 edit the same page and never run in parallel. Ticket 6 can follow 2 at any point.

Pointers for existing tickets: BLOG-11 and BLOG-20 build the agent panel and sources to 7.10; BLOG-19 styles Crepe's media blocks with the same tokens.

## 11. Not covered, risks

- **Browser tests (owner: yes).** The repo has vitest with jsdom only. jsdom cannot check the breakpoints, Tailwind's reset, the Crepe theme or focus rings, and the workspace rule asks for one browser test per user-visible flow. Ticket 0 sets it up; tickets 3 to 7 add one browser test per flow.
- **Click a problem to jump to its line** (spike result, BLOG-54: the mapping holds on the editor fixtures and the cases of `lib/line-map.test.ts`; the cards are clickable, with a runtime guard): the editor draws one block per top-level Markdown block (link reference definitions draw nothing, one empty paragraph may follow the last block); any other count is not trusted and a strip says the line was not found.
- **Browser Back with unsaved details:** in-app links are guarded; the browser's Back button is not. The text is still flushed when the editor unmounts; unsaved details can be lost. Acceptable unless the plan finds a cheap guard.
- **Preflight** changes default element styles; ticket 2 checks the editor and the Preview in a real browser (headings, lists, tables, maths, code).
- **Tailwind install:** native helper packages; if npm 12 blocks an install script, approve it only after reading what it does.
- **Revisions UI (BLOG-31)** is not in the mockup. Proposal, not approved: a "History" link under the Write step opens the list. Open owner question; the coordinator asks when BLOG-31 comes up.
- **Media and cover image (BLOG-19)** are not designed here.
