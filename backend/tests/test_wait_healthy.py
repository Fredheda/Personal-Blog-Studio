from conftest import FakeAz

SCRIPT = "scripts/wait-healthy.sh"
APPS = ("ca-blogstudio-web", "ca-blogstudio-api", "ca-blogapi")


def revision_checks(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("containerapp revision show")]


def test_it_passes_when_every_latest_revision_is_provisioned(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "10", "0")
    assert result.returncode == 0, result.stderr
    for app in APPS:
        assert f"{app}: {app}--rev1 is Provisioned" in result.stdout


def test_it_fails_fast_on_a_failed_revision(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "10", "0", env={"FAKE_PROVISIONING": "Failed"})
    assert result.returncode == 1
    assert "failed to provision" in result.stderr
    assert len(revision_checks(fake_az)) == 1  # it did not go on to the other apps


def test_it_times_out_while_a_revision_is_still_provisioning(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "0", "0", env={"FAKE_PROVISIONING": "Provisioning"})
    assert result.returncode == 1
    assert "timed out" in result.stderr
