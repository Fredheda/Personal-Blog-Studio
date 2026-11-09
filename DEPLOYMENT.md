# Deployment

How the blog studio and the blog read API reach Azure. Everything here changes shared Azure state: run a step only with the owner's explicit yes for that step.

## What exists

| Resource | Where | Note |
|---|---|---|
| `cae-blogstudio` | `rg-chatbot` | Container Apps environment, no Log Analytics (`az containerapp logs show --follow` for live logs) |
| `ca-blogstudio-web` | `rg-chatbot` | Next.js studio, external ingress, Easy Auth; only the owner's object ID (`BLOG_OWNER_OBJECT_ID`) is admitted, on top of the Entra enterprise app's "assignment required" setting (`setup-easyauth.sh`) |
| `ca-blogstudio-api` | `rg-chatbot` | FastAPI studio API, internal ingress, token validation (web identity only) |
| `ca-blogapi` | `rg-chatbot` | FastAPI read API `v1`, external hostname, token validation (approved callers only) |
| `id-blogstudio-acrpull`, `id-blogstudio-web`, `id-blogstudio-api`, `id-blogapi` | `rg-chatbot` | managed identities: registry pull, one runtime identity per app |
| `blog-drafts`, `blog-published` | `fhstorageportfolio` (`FrederikHedaPlayground`) | private containers; roles in `infra/storage.bicep` |
| images `blogstudio-web`, `blogstudio-api`, `blogapi` | `acrchatbotfredheda` | tagged with the full commit SHA and `latest` |

Scale: `minReplicas 0`, `maxReplicas 1`, 0.25 CPU / 0.5Gi each. Cost basis: the free allowance (owner decision); check Cost Management after the first month.

Roles (least privilege): the studio API identity is Storage Blob Data Contributor on both containers; the read API identity is Storage Blob Data Reader on `blog-published` only; both are Storage Blob Delegator on the account (to sign short-lived SAS URLs). Nothing uses a storage key, a connection string or a registry password.

## Order of operations (first deploy)

Each Entra or Azure write is a separate go from the owner. The scripts are dry runs until given `--apply` (`--run` for the gate).

1. `./scripts/setup-api-auth.sh`, then `--apply`: the API app registrations, the `Blog.Read` role, the two gate caller apps; writes the IDs, the tenant and the owner's object ID (`BLOG_OWNER_OBJECT_ID`) to `.env`.
2. `./scripts/setup-easyauth.sh`, then `--apply`: the login app, the owner assignment and the client secret (`BLOG_WEB_CLIENT_SECRET`, mode 600 in `.env`). Record the secret's expiry in `EXPIRATIONS.md`.
3. Add the real callers: `./scripts/approve-client.sh <client-id> --apply` for each (for the Portfolio backend: the client ID of its managed identity).
4. `./scripts/setup-storage.sh` (dry run: read the output), then `--apply` (shared account: one CORS rule, soft delete where it is off, one lifecycle rule; it never replaces other projects' settings).
5. `./scripts/build-push.sh <full-sha>` builds the three images with ACR Tasks (skips existing ones).
6. `./infra/deploy.sh <full-sha>`. It checks the SHA, the settings and the images before it touches Azure, and passes the parameters (including the Easy Auth client secret) in a mode-600 temporary file. `infra/deploy.sh` refuses to run without the `.env` values.
7. `./scripts/setup-easyauth.sh --apply` again: adds the web app's default hostname as a redirect URI.
8. `./scripts/live-gate.sh --run`: step 1 unauthenticated gets 401; step 2 an unapproved caller is refused; step 3 the approved caller reaches the app.
9. Later, its own change: DNS for `blog-studio.frederikheda.com`, the hostname bind and `customDomains` in `main.bicep`.

## Checks without Azure

- `cd backend && poetry run pytest -v`: script tests run against a fake `az`; the Bicep is checked structurally.
- `az bicep build --file infra/main.bicep --stdout >/dev/null`: compiles the template locally, no login.
- `shellcheck -x -P SCRIPTDIR scripts/*.sh scripts/lib/*.sh infra/deploy.sh`.

## Gotchas

- **Bicep `ingress` is authoritative.** A redeploy that omits `customDomains` wipes a bound domain. Bind `blog-studio.frederikheda.com` imperatively, then declare it in `main.bicep` in the same change.
- **Auth is mandatory.** `platform.enabled: true` must stay on all three auth configs: without it the config deploys cleanly and does nothing.
- **Never deploy a tag from local HEAD.** `deploy.sh` takes an explicit SHA for that reason.
- **Revision cutover is not instant.** After a deploy the old revision can answer for a short time; re-check before concluding a fix failed.
- **The read API allow list cannot be empty.** An empty `allowedApplications` could accept any caller with a valid token; `deploy.sh` and the Bicep both refuse it.
- **The shared storage account belongs to several projects.** `setup-storage.sh` only adds or merges; run its dry run first and read it.
- **CORS goes through the management API.** `setup-storage.sh` sets it with `az storage account blob-service-properties update --set cors.corsRules=...` (existing rules plus ours). The data-plane `az storage cors` commands take no `--auth-mode` and fall back to account keys, so they are not used. After the update `--apply` reads the rules back and stops with an error if our origin is missing or an existing rule was lost.
- **Entra writes are re-applied on every run.** `setup-api-auth.sh` and `setup-easyauth.sh` set the identifier URI, token version 2, the role and assignment-required each time, so a re-run repairs an app that was changed by hand. Two apps with the same display name stop the scripts. App lookups use an exact `--filter "displayName eq '<name>'"`: `az ad app list --display-name` matches every name that starts with the value (`blogapi` also matches `blogapi-gate-caller`), so never use it to find one app.
- **The gate's step 3 expects the app's own 404 until the read API exists** (BLOG-18): FastAPI's `{"detail":"Not Found"}` proves the request passed authentication and reached the app; then it becomes 200. An ingress 404 (the app is stopped or missing) has another body and fails the gate.
- **Admitting a second studio user** is an Entra assignment on `blogstudio-easyauth` plus a change to the Bicep: `ownerObjectId` becomes a list of object IDs in `allowedPrincipals.identities`. There is no script for it on purpose; the studio has one user.

## Limits

The registry is in legacy permission mode, so pushes cannot be scoped per repository. `deploy.sh` updates all three apps in one deployment; a failed deployment leaves the previous revisions serving. Rollback by SHA, the Deploy workflow and the registry purge arrive with BLOG-16.
