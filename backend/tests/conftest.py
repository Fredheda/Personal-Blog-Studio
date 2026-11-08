"""A fake `az` on PATH for the script tests.

It records every invocation (one line of arguments per call) and answers from
environment variables, so tests can check what a script would do to Azure
without touching it:

- FAKE_MISSING: comma list of `repo:tag`; `az acr repository show` exits 1 for them.
- FAKE_CORS: JSON printed for `az storage cors list` (default `[]`).
- FAKE_BLOB_SD / FAKE_CONTAINER_SD: `true` or `false` printed for the two soft-delete queries.
- FAKE_POLICY: JSON printed for `az storage account management-policy show`;
  when unset the command exits 1 (no policy yet).

For `az deployment group create` the fake copies the `--parameters @file` it
was given (content and permissions) to `$FAKE_LOG.params` and `$FAKE_LOG.mode`
at call time, because the script deletes the file when it exits.
"""

import os
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
  "storage cors list"*)
    echo "${FAKE_CORS:-[]}"; exit 0 ;;
  "storage account blob-service-properties show"*)
    case "$*" in
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
esac
exit 0
"""


@dataclass
class FakeAz:
    log: Path
    bin_dir: Path

    def run(
        self, script: str, *args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        full_env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_LOG": str(self.log),
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

    def side_file(self, suffix: str) -> str:
        """Text the fake saved next to the log (params, mode, paramfile)."""
        path = Path(f"{self.log}.{suffix}")
        return path.read_text().strip() if path.exists() else ""


@pytest.fixture
def fake_az(tmp_path: Path) -> FakeAz:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az = bin_dir / "az"
    az.write_text(FAKE_AZ)
    az.chmod(0o755)
    return FakeAz(log=tmp_path / "az.log", bin_dir=bin_dir)
