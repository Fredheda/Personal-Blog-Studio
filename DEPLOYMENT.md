# Deployment

How the blog studio and the blog read API reach Azure. Everything here changes shared Azure state: run a step only with the owner's explicit yes for that step.

## What exists

| Resource | Where | Note |
|---|---|---|
| `cae-blogstudio` | `rg-chatbot` | Container Apps environment, no Log Analytics (`az containerapp logs show --follow` for live logs) |
| `ca-blogstudio-web` | `rg-chatbot` | Next.js studio, external ingress, Easy Auth; only the owner's object ID (`BLOG_OWNER_OBJECT_ID`) is admitted, on top of the Entra enterprise app's "assignment required" setting (BLOG-15) |
| `ca-blogstudio-api` | `rg-chatbot` | FastAPI studio API, internal ingress, token validation (web identity only) |
| `ca-blogapi` | `rg-chatbot` | FastAPI read API `v1`, external hostname, token validation (approved callers only) |
| `id-blogstudio-acrpull`, `id-blogstudio-web`, `id-blogstudio-api`, `id-blogapi` | `rg-chatbot` | managed identities: registry pull, one runtime identity per app |
| `blog-drafts`, `blog-published` | `fhstorageportfolio` (`FrederikHedaPlayground`) | private containers; roles in `infra/storage.bicep` |
| images `blogstudio-web`, `blogstudio-api`, `blogapi` | `acrchatbotfredheda` | tagged with the full commit SHA and `latest` |

Scale: `minReplicas 0`, `maxReplicas 1`, 0.25 CPU / 0.5Gi each. Cost basis: the free allowance (owner decision); check Cost Management after the first month.

Roles (least privilege): the studio API identity is Storage Blob Data Contributor on both containers; the read API identity is Storage Blob Data Reader on `blog-published` only; both are Storage Blob Delegator on the account (to sign short-lived SAS URLs). Nothing uses a storage key, a connection string or a registry password.

## Order of operations (first deploy)

1. `./scripts/build-push.sh <full-sha>` builds the three images with ACR Tasks (skips existing ones).
2. Entra app registrations and the `.env` values (`.env.example`): the setup scripts of BLOG-15. The owner's object ID is `az ad signed-in-user show --query id -o tsv` run as the owner. `infra/deploy.sh` refuses to run without them.
3. `./scripts/setup-storage.sh` (dry run: read the output), then `./scripts/setup-storage.sh --apply` with the owner's yes. It adds one CORS rule, turns on soft delete where it is off and merges one lifecycle rule; it never replaces other projects' settings.
4. `./infra/deploy.sh <full-sha>` with the owner's yes. It checks the SHA, the settings and the images before it touches Azure, and passes the parameters (including the Easy Auth client secret) in a mode-600 temporary file.
5. The three-step live gate (BLOG-15): an unauthenticated request gets 401; an authenticated but unapproved caller is rejected; the approved caller succeeds.

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

## Limits

The registry is in legacy permission mode, so pushes cannot be scoped per repository. `deploy.sh` updates all three apps in one deployment; a failed deployment leaves the previous revisions serving. Rollback by SHA, the Deploy workflow and the registry purge arrive with BLOG-16.
