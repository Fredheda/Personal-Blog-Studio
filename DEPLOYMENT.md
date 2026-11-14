# Deployment

How the blog studio and the blog read API reach Azure. Everything here changes shared Azure state: run a step only with the owner's explicit yes for that step.

## What exists

| Resource | Where | Note |
|---|---|---|
| `cae-blogstudio` | `rg-chatbot` | Container Apps environment, no Log Analytics (`az containerapp logs show --follow` for live logs) |
| `ca-blogstudio-web` | `rg-chatbot` | Next.js studio, external ingress, Easy Auth; only the owner's object ID (`BLOG_OWNER_OBJECT_ID`) is admitted, on top of the Entra enterprise app's "assignment required" setting (`setup-easyauth.sh`); custom domain `blog-studio.frederikheda.com` once bound (step 9) |
| `ca-blogstudio-api` | `rg-chatbot` | FastAPI studio API, internal ingress, token validation (web identity only) |
| `ca-blogapi` | `rg-chatbot` | FastAPI read API `v1`, external hostname, token validation (approved callers only) |
| `id-blogstudio-acrpull`, `id-blogstudio-web`, `id-blogstudio-api`, `id-blogapi` | `rg-chatbot` | managed identities: registry pull, one runtime identity per app |
| `blog-drafts`, `blog-published` | `fhstorageportfolio` (`FrederikHedaPlayground`) | private containers; roles in `infra/storage.bicep` |
| images `blogstudio-web`, `blogstudio-api`, `blogapi` | `acrchatbotfredheda` | tagged with the full commit SHA and `latest` |

`ca-blogstudio-api` reads `BLOG_STUDIO_ORIGINS` (the web app's default hostname and custom domain); its same-origin guard rejects a request whose `Origin` is not listed. It is set by `infra/deploy.sh`.

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
9. Custom domain `blog-studio.frederikheda.com`, two owner gates plus a redeploy:
   1. `./scripts/bind-domain.sh dns` (dry run: shows `gddy dns add --dry-run` for the CNAME and the `asuid` TXT record), then `--apply`. If `gddy` asks for a login, the owner runs `gddy auth login --scope domains.domain:read --scope domains.dns:update`.
   2. Wait until `dig +short CNAME blog-studio.frederikheda.com` shows the app's hostname and `dig +short TXT asuid.blog-studio.frederikheda.com` shows the verification id.
   3. `./scripts/bind-domain.sh bind` (dry run), then `--apply`: adds the hostname, binds a free managed certificate, waits for it and writes `BLOG_WEB_CUSTOM_DOMAIN` and `BLOG_WEB_CERTIFICATE_NAME` to `.env`.
   4. `./infra/deploy.sh <sha>` once more: the Bicep now declares the domain, so deploys keep it.

## Deploy by button

Code changes reach the apps only through the manual **Deploy** workflow; infrastructure (Bicep, secrets, the custom domain) still goes through `./infra/deploy.sh` from the laptop.

One-time setup (each needs the owner's yes; both are dry runs until `--apply`):

1. `./scripts/setup-github-deploy.sh`, then `--apply`: the identities `id-blogstudio-gh-build` and `id-blogstudio-gh-deploy` with their roles, one federated credential each (trusting only the `production` environment; the subject is read from `gh api repos/<repo>/actions/oidc/customization/sub`, which for this repo is the immutable form `repo:<owner>@<owner id>/<name>@<repo id>:environment:production`, and the script stops when an existing credential trusts another subject: change it with `az identity federated-credential update`), the `production` environment (main only, the owner as required reviewer, admins cannot bypass) and the four `AZURE_*` repo secrets.
2. `./scripts/setup-acr-purge.sh` (read the dry run), then `--apply`: locks the running tags and creates the weekly purge task for this project's three repositories.

To deploy: `gh workflow run deploy.yml --ref main` (or Actions, Deploy, Run workflow; leave the SHA empty for the head of `main`). The run stops at `waiting`; the owner approves it in GitHub (Actions, the run, Review deployments). It validates the SHA, builds the three images if they do not exist (build identity), rolls the apps and swaps the tag locks (deploy identity), and waits for the new revisions. A coding agent never approves the run.

Rollback: the same button with an older commit SHA whose images still exist. Laptop fallback: `./scripts/ship.sh` (clean tree, builds and rolls `HEAD`).

Limits: the registry is in legacy permission mode, so pushes cannot be scoped per repository (the deploy identity's `AcrPush` also allows pushing). `redeploy.sh` updates the apps one at a time, so a failure between them leaves mixed versions until the button is pressed again. `infra/deploy.sh` needs the deployed SHA as its argument: it never defaults to the local `HEAD`, and it does not lock or unlock registry tags, so after an infra deploy at a new SHA press the Deploy button for that SHA (or run `./scripts/setup-acr-purge.sh --apply`) to lock the tag the apps now run.

## Checks without Azure

- `cd backend && poetry run pytest -v`: script tests run against a fake `az`; the Bicep is checked structurally.
- `az bicep build --file infra/main.bicep --stdout >/dev/null`: compiles the template locally, no login.
- `shellcheck -x -P SCRIPTDIR scripts/*.sh scripts/lib/*.sh infra/deploy.sh`.

### Storage tests against Azurite

Start Azurite (local only) on its default ports, run the contract against it, stop it. `UseDevelopmentStorage=true` is the SDK's shorthand for Azurite's built-in development account, so no key is written down here (a spelled-out key trips the secret scan even though it is public).

```bash
mkdir -p /tmp/azurite-blog && npx -y azurite --silent --skipApiVersionCheck --location /tmp/azurite-blog &
cd backend
export AZURITE_CONNECTION_STRING="UseDevelopmentStorage=true"
poetry run pytest tests/test_store_contract.py -q   # expect 20 passed
lsof -ti :10000 | xargs kill
```

CI does not run Azurite; the in-memory fake is held to the same contract by running this locally when `blog_core/store.py`, `azure_store.py` or the fake change.

## Gotchas

- **Bicep `ingress` is authoritative.** The custom domain is declared in `main.bicep` from `BLOG_WEB_CUSTOM_DOMAIN` and `BLOG_WEB_CERTIFICATE_NAME` (written by `bind-domain.sh`). A deploy without them while a domain is bound would unbind it, so `deploy.sh` refuses it. The CNAME must point directly at the app's generated hostname (never a proxy), and a CAA record on the zone, if one is ever added, must allow `digicert.com`; otherwise the managed certificate is not issued or renewed.
- **Auth is mandatory.** `platform.enabled: true` must stay on all three auth configs: without it the config deploys cleanly and does nothing.
- **Never deploy a tag from local HEAD.** `deploy.sh` takes an explicit SHA for that reason.
- **Revision cutover is not instant.** After a deploy the old revision can answer for a short time; re-check before concluding a fix failed.
- **The read API allow list cannot be empty.** An empty `allowedApplications` could accept any caller with a valid token; `deploy.sh` and the Bicep both refuse it.
- **The shared storage account belongs to several projects.** `setup-storage.sh` only adds or merges; run its dry run first and read it.
- **CORS goes through the management API.** `setup-storage.sh` sets it with `az storage account blob-service-properties update --set cors.corsRules=...` (existing rules plus ours). The data-plane `az storage cors` commands take no `--auth-mode` and fall back to account keys, so they are not used. After the update `--apply` reads the rules back and stops with an error if our origin is missing or an existing rule was lost.
- **Entra writes are re-applied on every run.** `setup-api-auth.sh` and `setup-easyauth.sh` set the identifier URI, token version 2, the role and assignment-required each time, so a re-run repairs an app that was changed by hand. Two apps with the same display name stop the scripts. App lookups use an exact `--filter "displayName eq '<name>'"`: `az ad app list --display-name` matches every name that starts with the value (`blogapi` also matches `blogapi-gate-caller`), so never use it to find one app.
- **The gate's step 3 expects the app's own 404 until the read API exists** (BLOG-18): the app's own 404 body (FastAPI's `{"detail":"Not Found"}`, or the problem+json the shared app factory sends since BLOG-29) proves the request passed authentication and reached the app; then it becomes 200. An ingress 404 (the app is stopped or missing) has another body and fails the gate.
- **Admitting a second studio user** is an Entra assignment on `blogstudio-easyauth` plus a change to the Bicep: `ownerObjectId` becomes a list of object IDs in `allowedPrincipals.identities`. There is no script for it on purpose; the studio has one user.

## Limits

The registry is in legacy permission mode, so pushes cannot be scoped per repository. `deploy.sh` updates all three apps in one deployment; a failed deployment leaves the previous revisions serving. Rollback is the Deploy button with an older SHA.
