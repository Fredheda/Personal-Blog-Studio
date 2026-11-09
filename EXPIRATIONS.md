# Expirations

Things that stop working on a date unless renewed.

| What | Created | Expires | Renew |
|---|---|---|---|
| Easy Auth client secret of the Entra app `blogstudio-easyauth` (`BLOG_WEB_CLIENT_SECRET` in `.env`, container app secret `microsoft-provider-authentication-secret`) | 2026-11-09 | 2028-11-09 (Entra end date 2028-11-09T01:32:26Z) | `./scripts/setup-easyauth.sh --apply --rotate`, then `./infra/deploy.sh <sha>`; the old secret keeps working until it expires, so after that redeploy delete the previous `blogstudio-easyauth` credential by key id (`az ad app credential list --id <app> --query "[].{id:keyId,end:endDateTime}"`, then `az ad app credential delete --id <app> --key-id <old>`) |
| Gate caller credentials | per run | one day | removed by `./scripts/live-gate.sh` on exit, and any stale `blog-gate` credential is cleared at the start of the next run; remove by hand from `blogapi-gate-caller` / `blogapi-gate-denied` if the script warns |
