import subprocess

from conftest import REPO_ROOT, FakeAz

HEAD = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=REPO_ROOT,
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()

IMAGES = [
    ("blogstudio-web", "frontend/Dockerfile", "frontend"),
    ("blogstudio-api", "backend/Dockerfile.studio", "backend"),
    ("blogapi", "backend/Dockerfile.blogapi", "backend"),
]


def source_and_run(snippet: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f"source scripts/lib/images.sh; {snippet}", "bash", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def builds(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("acr build")]


def test_is_sha_accepts_only_40_lowercase_hex() -> None:
    assert source_and_run('is_sha "$1"', "a" * 40).returncode == 0
    for bad in ("a" * 39, "a" * 41, "A" * 40, "main", "", "g" * 40):
        assert source_and_run('is_sha "$1"', bad).returncode != 0, bad


def test_the_image_list_names_the_three_apps() -> None:
    result = source_and_run('printf "%s\\n" "${IMAGES[@]}"')
    assert result.stdout.split() == [
        "blogstudio-web|ca-blogstudio-web|frontend/Dockerfile|frontend",
        "blogstudio-api|ca-blogstudio-api|backend/Dockerfile.studio|backend",
        "blogapi|ca-blogapi|backend/Dockerfile.blogapi|backend",
    ]


def test_build_push_rejects_a_non_sha_before_any_az_call(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/build-push.sh", "main")
    assert result.returncode == 1
    assert "main" in result.stderr
    assert fake_az.calls == []


def test_build_push_rejects_a_sha_that_is_not_a_commit(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/build-push.sh", "c" * 40)
    assert result.returncode == 1
    assert builds(fake_az) == []


def test_build_push_builds_the_three_missing_images_from_the_archive(
    fake_az: FakeAz,
) -> None:
    missing = ",".join(f"{repo}:{HEAD}" for repo, _, _ in IMAGES)
    result = fake_az.run("scripts/build-push.sh", HEAD, env={"FAKE_MISSING": missing})
    assert result.returncode == 0, result.stderr
    calls = builds(fake_az)
    assert len(calls) == 3
    for call, (repo, dockerfile, context) in zip(calls, IMAGES):
        assert "--registry acrchatbotfredheda" in call
        assert f"--file {dockerfile}" in call
        assert f"--image {repo}:latest" in call
        assert f"--image {repo}:{HEAD}" in call
        assert call.endswith(f" {context}")
    # Built from a temporary `git archive`, never from the working tree.
    for line in fake_az.build_dirs:
        assert not line.startswith(str(REPO_ROOT))
        assert line.endswith("has-dockerfile")


def test_build_push_skips_images_that_already_exist(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/build-push.sh", HEAD, env={"FAKE_MISSING": f"blogapi:{HEAD}"}
    )
    assert result.returncode == 0, result.stderr
    calls = builds(fake_az)
    assert len(calls) == 1 and f"--image blogapi:{HEAD}" in calls[0]
    assert "Skipping blogstudio-web" in result.stdout


def test_build_push_builds_nothing_when_all_images_exist(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/build-push.sh", HEAD)
    assert result.returncode == 0, result.stderr
    assert builds(fake_az) == []
    assert "Nothing to build" in result.stdout
