"""A fake `az` on PATH for the script tests.

It records every invocation (one line of arguments per call) and answers from
environment variables, so tests can check what a script would do to Azure
without touching it:

- FAKE_MISSING: comma list of `repo:tag`; `az acr repository show` exits 1 for them.
- FAKE_CORS: JSON printed for the `cors.corsRules` query of `az storage account
  blob-service-properties show` (ARM shape, default `[]`). `az storage cors ...`
  is rejected like the real CLI does (no `--auth-mode`).
- FAKE_BLOB_SD / FAKE_CONTAINER_SD: `true` or `false` printed for the two soft-delete queries.
- FAKE_POLICY: JSON printed for `az storage account management-policy show`;
  when unset the command exits 1 (no policy yet).
- FAKE_CUSTOM_DOMAINS: comma list of custom domains the web app has bound;
  FAKE_BINDING: bindingType printed by `az containerapp hostname list` (default
  SniEnabled); FAKE_CERT_STATES: see the certificate case.
- FAKE_GDDY_RECORDS / FAKE_GDDY_IGNORE_ADD and FAKE_DIG_CNAME / FAKE_DIG_TXT: see
  FAKE_GDDY and FAKE_DIG.

For `az deployment group create` the fake copies the `--parameters @file` it
was given (content and permissions) to `$FAKE_LOG.params` and `$FAKE_LOG.mode`
at call time, because the script deletes the file when it exits.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FAKE_AZ = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$*" in
  "acr repository show"*)
    image=$(echo "$*" | sed -E 's/.*--image ([^ ]+).*/\1/')
    case ",${FAKE_MISSING:-}," in *",$image,"*) exit 1 ;; esac
    exit 0 ;;
  "acr build"*)
    echo "$PWD $(test -f backend/Dockerfile.blogapi && echo has-dockerfile)" >> "$FAKE_LOG.build-dir"
    exit 0 ;;
  "storage cors"*)
    # The data-plane commands take no --auth-mode and fall back to account keys.
    echo "ERROR: unrecognized arguments: --auth-mode login" >&2; exit 2 ;;
  "storage account blob-service-properties update"*cors.corsRules=*)
    # Keep what was written so the read-back sees it. FAKE_CORS_IGNORE_UPDATE:
    # the write succeeds but changes nothing. FAKE_CORS_DROP_OTHERS: only the
    # last rule survives.
    all="$*"
    json=${all#*cors.corsRules=}
    if [ -n "${FAKE_CORS_IGNORE_UPDATE:-}" ]; then exit 0; fi
    if [ -n "${FAKE_CORS_DROP_OTHERS:-}" ]; then json=$(echo "$json" | jq -c '[.[-1]]'); fi
    echo "$json" > "$FAKE_LOG.cors"; exit 0 ;;
  "storage account blob-service-properties show"*)
    case "$*" in
      *cors.corsRules*)
        if [ -f "$FAKE_LOG.cors" ]; then cat "$FAKE_LOG.cors"; else echo "${FAKE_CORS:-[]}"; fi ;;
      *containerDeleteRetentionPolicy*) echo "${FAKE_CONTAINER_SD:-false}" ;;
      *) echo "${FAKE_BLOB_SD:-false}" ;;
    esac
    exit 0 ;;
  "storage account management-policy show"*)
    if [ -z "${FAKE_POLICY:-}" ]; then exit 1; fi
    echo "$FAKE_POLICY"; exit 0 ;;
  "deployment group create"*)
    file=$(echo "$*" | sed -E 's/.*--parameters @([^ ]+).*/\1/')
    if [ -f "$file" ]; then
      cp "$file" "$FAKE_LOG.params"
      ls -l "$file" | cut -c1-10 > "$FAKE_LOG.mode"
      echo "$file" > "$FAKE_LOG.paramfile"
    fi
    exit 0 ;;
  "account show"*) echo "tenant-1"; exit 0 ;;
  "ad signed-in-user show"*) echo "owner-oid"; exit 0 ;;
  "ad app list"*)
    # Like the live service: --display-name matches names that START with the
    # value; --filter "displayName eq 'x'" matches the exact name only.
    st="$FAKE_LOG.state"
    case "$*" in
      *"--filter"*)
        name=$(echo "$*" | sed -E "s/.*displayName eq '([^']+)'.*/\1/")
        matches=$(ls "$st" 2>/dev/null | grep -x "app-$name" || true) ;;
      *)
        name=$(echo "$*" | sed -E 's/.*--display-name ([^ ]+).*/\1/')
        matches=$(ls "$st" 2>/dev/null | grep "^app-$name" || true) ;;
    esac
    case "$*" in
      *"length(@)"*)
        case ",${FAKE_DUP_APPS:-}," in
          *",$name,"*) echo 2 ;;
          *) printf '%s\n' "$matches" | grep -c . ;;
        esac ;;
      *)
        first=$(printf '%s\n' "$matches" | head -1)
        if [ -n "$first" ]; then cat "$st/$first"; fi ;;
    esac
    exit 0 ;;
  "ad app create"*)
    name=$(echo "$*" | sed -E 's/.*--display-name ([^ ]+).*/\1/')
    mkdir -p "$FAKE_LOG.state"
    echo "appid-$name" > "$FAKE_LOG.state/app-$name"
    echo "appid-$name"; exit 0 ;;
  "ad app show"*)
    id=$(echo "$*" | sed -E 's/.*--id ([^ ]+).*/\1/'); echo "obj-$id"; exit 0 ;;
  "ad app update"*) exit 0 ;;
  "ad app credential reset"*)
    app=$(echo "$*" | sed -E 's/.*--id ([^ ]+).*/\1/')
    mkdir -p "$FAKE_LOG.state"
    n=$(cat "$FAKE_LOG.state/secrets" 2>/dev/null || echo 0); n=$((n+1))
    echo "$n" > "$FAKE_LOG.state/secrets"
    echo "key-$n" >> "$FAKE_LOG.state/keys-$app"
    echo "secret-$n"; exit 0 ;;
  "ad app credential list"*)
    # Stateful: keys added by `reset`, plus FAKE_STALE_KEYS ("app:key,app:key")
    # left over from an earlier run, minus the ones already deleted.
    app=$(echo "$*" | sed -E 's/.*--id ([^ ]+).*/\1/')
    st="$FAKE_LOG.state"; mkdir -p "$st"
    {
      cat "$st/keys-$app" 2>/dev/null
      echo "${FAKE_STALE_KEYS:-}" | tr ',' '\n' | grep "^$app:" | cut -d: -f2
    } | grep -v '^$' | while read -r k; do
      grep -qx "$k" "$st/deleted" 2>/dev/null || echo "$k"
    done
    # FAKE_PERSISTENT_KEYS ("app:key"): listed again even after a delete.
    echo "${FAKE_PERSISTENT_KEYS:-}" | tr ',' '\n' | grep "^$app:" | cut -d: -f2
    exit 0 ;;
  "ad app credential delete"*)
    key=$(echo "$*" | sed -E 's/.*--key-id ([^ ]+).*/\1/')
    mkdir -p "$FAKE_LOG.state"; echo "$key" >> "$FAKE_LOG.state/deleted"
    exit 0 ;;
  "ad sp show"*)
    id=$(echo "$*" | sed -E 's/.*--id ([^ ]+).*/\1/')
    # A GUID is a real client ID (e.g. a managed identity): its service principal exists.
    if echo "$id" | grep -qE '^[0-9a-fA-F]{8}-'; then echo "sp-$id"; exit 0; fi
    [ -f "$FAKE_LOG.state/sp-$id" ] || exit 1
    echo "sp-$id"; exit 0 ;;
  "ad sp create"*)
    id=$(echo "$*" | sed -E 's/.*--id ([^ ]+).*/\1/')
    mkdir -p "$FAKE_LOG.state"; touch "$FAKE_LOG.state/sp-$id"
    echo "sp-$id"; exit 0 ;;
  "rest --method GET"*) echo "${FAKE_ASSIGNED_COUNT:-0}"; exit 0 ;;
  "rest --method PATCH"*|"rest --method POST"*) exit 0 ;;
  "containerapp show"*)
    if [ -n "${FAKE_NO_WEB_APP:-}" ]; then exit 1; fi
    case "$*" in
      *customDomainVerificationId*) echo "verify-123" ;;
      # Domains whose binding is SniEnabled default to all of FAKE_CUSTOM_DOMAINS;
      # FAKE_SNI_DOMAINS (even empty) overrides, to model a half-done bind.
      *bindingType*) printf '%s\n' "${FAKE_SNI_DOMAINS-${FAKE_CUSTOM_DOMAINS:-}}" | tr ',' '\n' | grep . || true ;;
      *customDomains*) printf '%s\n' "${FAKE_CUSTOM_DOMAINS:-}" | tr ',' '\n' | grep . || true ;;
      *) echo "app.example.test" ;;
    esac
    exit 0 ;;
  "containerapp list"*)
    # FAKE_LIST_FAILS: the call fails (auth, network); FAKE_NO_WEB_APP: no apps.
    if [ -n "${FAKE_LIST_FAILS:-}" ]; then echo "ERROR: (AuthorizationFailed) simulated" >&2; exit 1; fi
    if [ -n "${FAKE_NO_WEB_APP:-}" ]; then echo 0; else echo 1; fi
    exit 0 ;;
  "containerapp hostname list"*)
    echo "${FAKE_BINDING:-SniEnabled}"; exit 0 ;;
  "containerapp env certificate list"*)
    # FAKE_CERT_STATES: comma list of provisioning states returned by successive
    # calls (the last one repeats); "none" = no certificate yet. Default: Succeeded.
    st="$FAKE_LOG.state"; mkdir -p "$st"
    n=$(cat "$st/certcalls" 2>/dev/null || echo 0); echo $((n+1)) > "$st/certcalls"
    IFS=',' read -r -a states <<<"${FAKE_CERT_STATES:-Succeeded}"
    i=$n; [ "$i" -ge "${#states[@]}" ] && i=$((${#states[@]}-1))
    s=${states[$i]}
    if [ "$s" = none ]; then echo '[]'; else echo "[{\"name\":\"mc-cae-blogstudio-blog-studio-1234\",\"state\":\"$s\"}]"; fi
    exit 0 ;;
esac
exit 0
"""


@dataclass
class FakeAz:
    log: Path
    bin_dir: Path
    real_jq: str = "jq"

    def run(
        self, script: str, *args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        full_env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_LOG": str(self.log),
            "REAL_JQ": self.real_jq,
            **(env or {}),
        }
        return subprocess.run(
            ["bash", script, *args],
            cwd=REPO_ROOT,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    @property
    def calls(self) -> list[str]:
        return self.log.read_text().splitlines() if self.log.exists() else []

    @property
    def build_dirs(self) -> list[str]:
        build_log = Path(f"{self.log}.build-dir")
        return build_log.read_text().splitlines() if build_log.exists() else []

    @property
    def jq_calls(self) -> list[str]:
        """Arguments of every `jq` call, as another process could see them."""
        jq_log = Path(f"{self.log}.jq")
        return jq_log.read_text().splitlines() if jq_log.exists() else []

    def run_shell(
        self, command: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run a bash snippet with the fakes on PATH, from the repo root."""
        full_env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_LOG": str(self.log),
            "REAL_JQ": self.real_jq,
            **(env or {}),
        }
        return subprocess.run(
            ["bash", "-c", command],
            cwd=REPO_ROOT,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    @property
    def state_dir(self) -> Path:
        return Path(f"{self.log}.state")

    @property
    def curl_calls(self) -> list[str]:
        curl_log = Path(f"{self.log}.curl")
        return curl_log.read_text().splitlines() if curl_log.exists() else []

    def side_file(self, suffix: str) -> str:
        """Text the fake saved next to the log (params, mode, paramfile)."""
        path = Path(f"{self.log}.{suffix}")
        return path.read_text().strip() if path.exists() else ""


# Logs the arguments of every `jq` call (what another local process could read
# from the process list), then runs the real jq.
FAKE_JQ = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG.jq"
exec "$REAL_JQ" "$@"
"""


# Stands in for curl in the live gate. Token requests read the form file given
# with `-d @file`; API requests read the header file given with `-H @file` and
# write a body to the `-o file` they were given.
# FAKE_DENIED_TOKEN / FAKE_APPROVED_TOKEN: refused | notready | none | issued (default).
# FAKE_UNAUTH_CODE (401), FAKE_DENIED_CODE (403), FAKE_APPROVED_CODE (404).
# FAKE_APPROVED_BODY: body for the approved caller's answer (default: the app's
# own 404 body, {"detail":"Not Found"}, or {} for other codes).
FAKE_CURL = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG.curl"
form=""; hdr=""; out=""; prev=""
for a in "$@"; do
  case "$prev" in -d) form=${a#@} ;; -H) hdr=${a#@} ;; -o) out=$a ;; esac
  prev=$a
done
case "$*" in
  *oauth2/v2.0/token*)
    cid=$(sed -E 's/.*client_id=([^&]*).*/\1/' "$form")
    case "$cid" in
      *gate-denied*) mode=${FAKE_DENIED_TOKEN:-issued} ;;
      *) mode=${FAKE_APPROVED_TOKEN:-issued} ;;
    esac
    case "$mode" in
      refused) echo '{"error":"invalid_grant","error_description":"AADSTS501051: Application is not assigned to a role for this resource"}' ;;
      none) echo '{"error":"invalid_client","error_description":"AADSTS70002: other failure"}' ;;
      notready)
        n=$(cat "$FAKE_LOG.notready" 2>/dev/null || echo 0); echo $((n+1)) > "$FAKE_LOG.notready"
        if [ "$n" -lt 1 ]; then
          echo '{"error":"invalid_client","error_description":"AADSTS7000215: Invalid client secret provided"}'
        else
          echo "{\"access_token\":\"tok-$cid\"}"
        fi ;;
      *) echo "{\"access_token\":\"tok-$cid\"}" ;;
    esac ;;
  *)
    write_body() { if [ -n "$out" ] && [ "$out" != /dev/null ]; then printf '%s' "$1" > "$out"; fi; }
    if [ -z "$hdr" ]; then write_body '{"detail":"Unauthorized"}'; echo "${FAKE_UNAUTH_CODE:-401}"; exit 0; fi
    if grep -q 'gate-denied' "$hdr"; then
      write_body '{}'; echo "${FAKE_DENIED_CODE:-403}"
    else
      code=${FAKE_APPROVED_CODE:-404}
      if [ "$code" = 404 ]; then default='{"detail":"Not Found"}'; else default='{}'; fi
      write_body "${FAKE_APPROVED_BODY:-$default}"; echo "$code"
    fi ;;
esac
"""


# Stands in for gddy. `dns list` prints {"data": [...]} (the envelope gddy uses
# for every command) for the records of one type and name; `dns add` appends to
# a state file unless --dry-run or FAKE_GDDY_IGNORE_ADD.
# FAKE_GDDY_RECORDS: preset records, one "TYPE|name|data" per line.
FAKE_GDDY = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG.gddy"
state="$FAKE_LOG.gddy-records"
touch "$state"
[ "$1 $2" = "dns list" ] || [ "$1 $2" = "dns add" ] || exit 2
cmd=$2; shift 2
zone=$1; shift
type=""; name=""; data=""; dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --type) type=$2; shift ;;
    --name) name=$2; shift ;;
    --data) data=$2; shift ;;
    --dry-run) dry=1 ;;
  esac
  shift
done
if [ "$cmd" = list ]; then
  { printf '%s\n' "${FAKE_GDDY_RECORDS:-}"; cat "$state"; } | grep . |
    awk -F'|' -v t="$type" -v n="$name" '$1==t && $2==n' |
    jq -R -s -c 'split("\n") | map(select(length>0) | split("|") | {name: .[1], data: .[2], ttl: 3600}) | {data: .}'
  exit 0
fi
if [ "$dry" = 0 ] && [ -z "${FAKE_GDDY_IGNORE_ADD:-}" ]; then echo "$type|$name|$data" >> "$state"; fi
echo '{"data":[]}'
"""

# Stands in for dig +short. FAKE_DIG_CNAME and FAKE_DIG_TXT are printed as dig
# would (CNAME with a trailing dot, TXT in quotes).
FAKE_DIG = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG.dig"
case "$*" in
  *"CNAME "*) printf '%s\n' "${FAKE_DIG_CNAME:-}" ;;
  *"TXT "*) printf '%s\n' "${FAKE_DIG_TXT:-}" ;;
esac
"""


@pytest.fixture
def fake_az(tmp_path: Path) -> FakeAz:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az = bin_dir / "az"
    az.write_text(FAKE_AZ)
    az.chmod(0o755)
    jq = bin_dir / "jq"
    jq.write_text(FAKE_JQ)
    jq.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(0o755)
    for tool_name, body in (("gddy", FAKE_GDDY), ("dig", FAKE_DIG)):
        tool = bin_dir / tool_name
        tool.write_text(body)
        tool.chmod(0o755)
    return FakeAz(
        log=tmp_path / "az.log",
        bin_dir=bin_dir,
        real_jq=shutil.which("jq") or "jq",
    )
