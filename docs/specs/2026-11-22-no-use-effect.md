# No `useEffect`: a lint rule, one folder of named hooks, and the removal

- **Ticket:** BLOG-61 (owner, 2026-11-22: "I don't like the use-effect thing in javascript as it seems like almost always it is a bit of an anti pattern. Can we add a lint rule against it remove use-effect across repos?"; decision 583 A: effects are banned everywhere except one small folder of named hooks, no new dependency).
- **Status:** proposed. Plan: `docs/plans/2026-11-22-no-use-effect.md`.

## Intent

Most effects in a component either compute something that can be derived, or react to something a handler already knows. The rest synchronise React with something outside it (a timer, a window listener, a request, a third-party editor, an object with a close step). React has no other primitive for those, so they cannot be deleted, only given one guarded place and a name. After this change a component never calls an effect hook; each use site says what it does by the name of the hook it calls.

## Goals

- Rule: ESLint core only, level `error`, in `frontend/eslint.config.mjs`. `no-restricted-imports` rejects `useEffect`, `useLayoutEffect` and `useInsertionEffect` imported from `react` (a renamed import is caught), and `no-restricted-syntax` rejects `React.useEffect` and `React["useEffect"]`. The folder `frontend/effects/` is exempt by path, never by a line. Tests are not exempt.
- Folder `frontend/effects/`: small hooks named for what they synchronise with, each with a test: `useLatest`, `useWindowListener`, `useInterval`, `useRequest`, `useController`, `useWidget`, `useFocusReturn`. Nothing generic such as `useMount` or `useOnChange`: a generic wrapper would be `useEffect` under another name.
- Every current use is removed or moved into the folder; behaviour is unchanged, the editor's autosave life cycle included (the existing component and browser tests are the check, plus a test per hook).
- A directive that switches off the two restricted rules fails the `comment-content` rule (extra guard patterns), so the folder stays the only exemption.
- The cheat sheet (what to write instead of an effect) goes into `docs/development.md`.
- Each behaviour has a failing test written and run red before the code.

## Non-goals

- No data-loading library and no React 19-only primitive: the hooks keep the exact semantics of the effects they replace. A library for the two request sites is a separate decision.
- No change to what a user sees or to the API.

## The hooks

| Hook | Replaces | Contract |
|---|---|---|
| `useLatest(value)` | a ref that is re-assigned in an effect | returns a ref holding the value of the latest render |
| `useWindowListener(type, handler, enabled = true)` | `addEventListener` on `window` in an effect | the latest handler is called; removed when disabled or on unmount |
| `useInterval(fn, ms)` | `setInterval` in an effect | the latest `fn` on every tick; `null` pauses; cleared on unmount |
| `useRequest(request, key, { onResult, onError, enabled })` | a request started in an effect | runs again when `key` changes; an answer that arrives after the key changed or the owner unmounted is dropped |
| `useController(create, key)` | an object with a close step created in an effect | `create(alive)` runs once per key; the previous controller is closed first; `alive()` is false from the cleanup on; returns a ref to the controller |
| `useWidget(mount)` | a third-party widget created on a DOM node in an effect | returns a ref callback; `mount(root)` returns its cleanup; read once at attach |
| `useFocusReturn(target)` | focus on mount and return on unmount | focuses `target` when it mounts and gives the focus back to the element that had it |

## The eleven uses today

| Place | Before | After |
|---|---|---|
| `components/useModal.ts` | focus on mount, restore on unmount | `useFocusReturn` |
| `components/PostEditor.tsx` | load the post | `useRequest` |
| `components/PostEditor.tsx` | the 30 s display clock | `useInterval` |
| `components/PostEditor.tsx` | the autosave controller | `useController` |
| `components/PostEditor.tsx` | the `beforeunload` warning | `useWindowListener` |
| `components/Posts.tsx` | load the list | `useRequest` |
| `components/CrepeEditor.tsx` | latest-callback refs | `useLatest` |
| `components/CrepeEditor.tsx` | create and destroy the editor | `useWidget` |
| `lib/use-check.ts` | latest-callback ref | `useLatest` |
| `lib/use-check.ts` | the check request on every save | `useRequest` |
| `components/PostEditor.test.tsx` | a stand-in editor | `useWidget` |

## Constraints

- `PostEditor.tsx` is edited by other tickets that never run in parallel with this one; the plan names each effect by what it does, so the executor re-reads the file and applies the same replacement if the surrounding code moved.
- No new dependency, no workflow change.
- Files this PR touches follow the comment standard: the floor and the content rule apply, so the cleanup commit cuts the long effect comments (what stays is listed under `Comments:` in the PR description).

## Left to the builder

The exact wording of the lint message, helper names inside the hooks, the wording of the cheat sheet.

## Owner decisions this rests on

583 A (one exempt folder per repo, no new dependency). My calls, for the reviewer to check: seven hooks (`useLatest` and `useFocusReturn` included although the design lists five), `useRequest` keeps the effect's callbacks-based shape so `PostEditor` adopts a loaded post exactly as before, the request key is one memoised object.
