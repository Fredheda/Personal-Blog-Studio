import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yml"
LOCAL = REPO / "scripts" / "ci-local.sh"


def _ci_job_ids() -> list[str]:
    jobs_block = CI.read_text().split("\njobs:\n", 1)[1]
    return re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", jobs_block, re.M)


def test_ci_defines_the_backend_jobs():
    assert {"workflow-lint", "backend-test", "backend-lint"} <= set(_ci_job_ids())


def test_ci_local_runs_every_ci_job():
    script = LOCAL.read_text()
    for job_id in _ci_job_ids():
        assert f'step "{job_id}"' in script, job_id
