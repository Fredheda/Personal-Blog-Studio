from conftest import FakeAz

SCRIPT = "scripts/redeploy.sh"
SHA = "a" * 40
OLD = "b" * 40
APPS = ("ca-blogstudio-web", "ca-blogstudio-api", "ca-blogapi")
REPOS = ("blogstudio-web", "blogstudio-api", "blogapi")
REGISTRY = "acrchatbotfredheda.azurecr.io"


def running(*tags: str) -> dict[str, str]:
    """FAKE_IMAGE_<APP> for each app, running the given tag."""
    return {
        f"FAKE_IMAGE_{app.upper().replace('-', '_')}": f"{REGISTRY}/{repo}:{tag}"
        for app, repo, tag in zip(APPS, REPOS, tags, strict=True)
    }


def updates(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("containerapp update")]


def locks(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("acr repository update")]


def lock_call(repo: str, tag: str, locked: bool) -> str:
    return (
        f"acr repository update -n acrchatbotfredheda --image {repo}:{tag} "
        f"--delete-enabled {'false' if locked else 'true'} "
        "--write-enabled true --output none"
    )


def test_no_sha_or_a_bad_sha_is_refused_before_any_az_call(fake_az: FakeAz) -> None:
    for args in ((), ("main",), ("A" * 40,), ("a" * 39,)):
        assert fake_az.run(SCRIPT, *args).returncode == 2, args
    assert fake_az.calls == []


def test_it_refuses_when_any_image_is_missing_and_changes_nothing(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(SCRIPT, SHA, env={"FAKE_MISSING": f"blogapi:{SHA}"})
    assert result.returncode == 1
    assert "blogapi" in result.stderr
    assert updates(fake_az) == [] and locks(fake_az) == []


def test_it_rolls_the_three_apps_to_the_sha_in_order(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, SHA, env=running(OLD, OLD, OLD))
    assert result.returncode == 0, result.stderr
    ups = updates(fake_az)
    assert len(ups) == 3
    for up, app, repo in zip(ups, APPS, REPOS, strict=True):
        assert f"-n {app} " in up
        assert f"--image {REGISTRY}/{repo}:{SHA}" in up


def test_it_reads_the_running_tags_before_it_changes_anything(
    fake_az: FakeAz,
) -> None:
    fake_az.run(SCRIPT, SHA, env=running(OLD, OLD, OLD))
    calls = fake_az.calls
    first_update = next(
        i for i, c in enumerate(calls) if c.startswith("containerapp update")
    )
    reads = [
        i
        for i, c in enumerate(calls)
        if c.startswith("containerapp show") and "template.containers" in c
    ]
    assert len(reads) == 3 and all(i < first_update for i in reads)


def test_it_locks_the_new_tags_and_unlocks_the_old_ones(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, SHA, env=running(OLD, OLD, OLD))
    assert result.returncode == 0, result.stderr
    got = locks(fake_az)
    for repo in REPOS:
        assert lock_call(repo, SHA, True) in got
        assert lock_call(repo, OLD, False) in got
    assert len(got) == 6


def test_it_never_unlocks_latest_or_the_sha_it_is_already_on(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, SHA, env=running("latest", SHA, OLD))
    assert result.returncode == 0, result.stderr
    got = locks(fake_az)
    unlocks = [c for c in got if "--delete-enabled true" in c]
    assert unlocks == [lock_call("blogapi", OLD, False)]
    assert not any(":latest" in c for c in got)


def test_a_failed_update_changes_no_lock(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT, SHA, env={**running(OLD, OLD, OLD), "FAKE_FAIL_UPDATE": "ca-blogapi"}
    )
    assert result.returncode != 0
    assert locks(fake_az) == []
