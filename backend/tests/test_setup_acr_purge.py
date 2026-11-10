from conftest import FakeAz

SCRIPT = "scripts/setup-acr-purge.sh"
OLD = "b" * 40
APPS = ("ca-blogstudio-web", "ca-blogstudio-api", "ca-blogapi")
REPOS = ("blogstudio-web", "blogstudio-api", "blogapi")
RUNNING = {
    f"FAKE_IMAGE_{app.upper().replace('-', '_')}": f"acrchatbotfredheda.azurecr.io/{repo}:{OLD}"
    for app, repo in zip(APPS, REPOS, strict=True)
}


def calls(fake_az: FakeAz, prefix: str) -> list[str]:
    return [c for c in fake_az.calls if c.startswith(prefix)]


def test_an_unknown_flag_is_refused(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--create")
    assert result.returncode == 2
    assert fake_az.calls == []


def test_the_default_locks_nothing_creates_no_task_and_runs_only_a_dry_run(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(SCRIPT, env=RUNNING)
    assert result.returncode == 0, result.stderr
    assert calls(fake_az, "acr repository update") == []
    assert calls(fake_az, "acr task create") == []
    (run,) = calls(fake_az, "acr run")
    assert "--dry-run" in run
    assert result.stdout.count("would lock") == 3


def test_the_filters_name_only_this_projects_sha_tags(fake_az: FakeAz) -> None:
    fake_az.run(SCRIPT, env=RUNNING)
    (run,) = calls(fake_az, "acr run")
    for repo in REPOS:
        assert f"--filter '{repo}:^[0-9a-f]{{40}}$'" in run
    assert run.count("--filter") == 3
    assert "--ago 30d --keep 10 --untagged" in run
    assert "--include-locked" not in run


def test_apply_locks_the_running_tags_and_creates_the_weekly_task_without_dry_run(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(SCRIPT, "--apply", env=RUNNING)
    assert result.returncode == 0, result.stderr
    locked = calls(fake_az, "acr repository update")
    assert len(locked) == 3 and all("--delete-enabled false" in c for c in locked)
    for repo in REPOS:
        assert any(f"--image {repo}:{OLD} " in c for c in locked), repo
    (create,) = calls(fake_az, "acr task create")
    assert "-n purge-blogstudio-images" in create
    assert "--schedule 0 3 * * Sun" in create
    assert "--dry-run" not in create and "--include-locked" not in create


def test_apply_replaces_an_existing_task(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply", env=RUNNING)
    assert result.returncode == 0, result.stderr
    verbs = [c.split()[2] for c in fake_az.calls if c.startswith("acr task ")]
    assert verbs == ["show", "delete", "create"]


def test_a_running_tag_that_is_not_a_sha_is_not_locked(fake_az: FakeAz) -> None:
    env = {
        **RUNNING,
        "FAKE_IMAGE_CA_BLOGAPI": "acrchatbotfredheda.azurecr.io/blogapi:latest",
    }
    result = fake_az.run(SCRIPT, "--apply", env=env)
    locked = calls(fake_az, "acr repository update")
    assert len(locked) == 2 and not any("blogapi:" in c for c in locked)
    assert "not locking" in result.stdout
