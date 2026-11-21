import json

from conftest import FakeAz

SCRIPT = "scripts/setup-dev-storage.sh"
ACCOUNT = (
    "/subscriptions/sub-1/resourceGroups/FrederikHedaPlayground"
    "/providers/Microsoft.Storage/storageAccounts/fhstorageportfolio"
)
BASE = f"{ACCOUNT}/blobServices/default/containers"
DRAFTS = f"{BASE}/blog-drafts-dev"
PUBLISHED = f"{BASE}/blog-published-dev"


def assignment(role: str, scope: str) -> dict:
    return {"roleDefinitionName": role, "scope": scope}


def roles(*items: dict) -> dict:
    return {"FAKE_ROLES": json.dumps(list(items))}


def changes(fake_az: FakeAz) -> list[str]:
    return [
        c
        for c in fake_az.calls
        if c.startswith(("storage container-rm create", "role assignment create"))
    ]


def test_a_dry_run_prints_every_change_and_changes_nothing(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT)
    assert result.returncode == 0, result.stderr
    assert changes(fake_az) == []
    for name in ("blog-drafts-dev", "blog-published-dev"):
        assert f"-n {name} --public-access off" in result.stdout
    assert f"--scope {DRAFTS}" in result.stdout
    assert f"--scope {PUBLISHED}" in result.stdout
    assert "Storage Blob Data Contributor" in result.stdout


def test_every_role_is_scoped_to_one_dev_container_never_the_account(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(SCRIPT)
    scopes = [
        line.split("--scope ", 1)[1].split(" ", 1)[0]
        for line in result.stdout.splitlines()
        if line.startswith("+ az role assignment create")
    ]
    assert sorted(scopes) == [DRAFTS, PUBLISHED]


def test_apply_creates_both_containers_and_roles_then_reads_them_back(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(SCRIPT, "--apply")
    assert result.returncode == 0, result.stderr
    assert len(changes(fake_az)) == 4
    assert result.stdout.count("public access None") == 2
    assert "no blob data role outside the dev containers" in result.stdout


def test_a_role_that_exists_is_not_created_again(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env=roles(assignment("Storage Blob Data Contributor", DRAFTS)),
    )
    assert result.returncode == 0, result.stderr
    created = [c for c in changes(fake_az) if c.startswith("role assignment create")]
    assert len(created) == 1 and PUBLISHED in created[0]


def test_scopes_are_compared_without_regard_to_case(fake_az: FakeAz) -> None:
    # Azure lists one scope as /resourcegroups/... and others as /resourceGroups/...
    lowered = DRAFTS.replace("/resourceGroups/", "/resourcegroups/")
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env=roles(assignment("Storage Blob Data Contributor", lowered)),
    )
    assert result.returncode == 0, result.stderr
    created = [c for c in changes(fake_az) if c.startswith("role assignment create")]
    assert len(created) == 1 and PUBLISHED in created[0]


def test_any_blob_data_role_outside_the_dev_containers_stops_everything(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env=roles(assignment("Storage Blob Data Reader", ACCOUNT)),
    )
    assert result.returncode == 1
    assert "outside the dev containers" in result.stderr
    assert changes(fake_az) == []


def test_other_roles_do_not_matter(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env=roles(
            assignment("Owner", "/subscriptions/sub-1"),
            assignment("Storage File Data SMB Share Contributor", ACCOUNT),
        ),
    )
    assert result.returncode == 0, result.stderr


def test_a_name_that_is_not_a_dev_container_is_refused(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT, "--apply", env={"BLOG_DEV_DRAFTS_CONTAINER": "blog-drafts"}
    )
    assert result.returncode == 1
    assert "does not end in -dev" in result.stderr
    assert changes(fake_az) == []


def test_a_container_that_is_public_fails_the_read_back(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply", env={"FAKE_PUBLIC_ACCESS": "Blob"})
    assert result.returncode == 1
    assert "public access" in result.stderr
