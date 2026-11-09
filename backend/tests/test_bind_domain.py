import subprocess
from pathlib import Path

from conftest import FakeAz

SCRIPT = "scripts/bind-domain.sh"
HOST = "blog-studio.frederikheda.com"
FQDN = "app.example.test"
VERIFY = "verify-123"
CERT = "mc-cae-blogstudio-blog-studio-1234"
READY = {"FAKE_DIG_CNAME": f"{FQDN}.", "FAKE_DIG_TXT": f'"{VERIFY}"'}
BOTH = "\n".join([f"CNAME|blog-studio|{FQDN}", f"TXT|asuid.blog-studio|{VERIFY}"])


def run(
    fake_az: FakeAz, tmp_path: Path, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return fake_az.run(
        SCRIPT,
        *args,
        env={
            "BLOG_ENV_FILE": str(tmp_path / ".env"),
            "CERT_SLEEP": "0",
            "CERT_TRIES": "3",
            **env,
        },
    )


def gddy_calls(fake_az: FakeAz) -> list[str]:
    path = Path(f"{fake_az.log}.gddy")
    return path.read_text().splitlines() if path.exists() else []


def adds(fake_az: FakeAz) -> list[str]:
    return [c for c in gddy_calls(fake_az) if c.startswith("dns add")]


def real_adds(fake_az: FakeAz) -> list[str]:
    return [c for c in adds(fake_az) if "--dry-run" not in c]


def writes(fake_az: FakeAz) -> list[str]:
    prefixes = ("containerapp hostname add", "containerapp hostname bind")
    return [c for c in fake_az.calls if c.startswith(prefixes)]


def env_text(tmp_path: Path) -> str:
    path = tmp_path / ".env"
    return path.read_text() if path.exists() else ""


def test_bad_usage_is_refused_before_any_call(fake_az: FakeAz, tmp_path: Path) -> None:
    for args in ((), ("nope",), ("dns", "--yes"), ("dns", "--apply", "extra")):
        result = run(fake_az, tmp_path, *args)
        assert result.returncode == 2, args
    assert fake_az.calls == [] and gddy_calls(fake_az) == []


def test_only_a_subdomain_of_a_two_part_zone_is_accepted(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    for host in (
        "frederikheda.com",
        "a.b.frederikheda.com",
        "Blog_Studio.frederikheda.com",
    ):
        result = run(fake_az, tmp_path, "dns", BLOG_STUDIO_DOMAIN=host)
        assert result.returncode == 2, host
    assert fake_az.calls == []


def test_an_undeployed_app_stops_both_phases(fake_az: FakeAz, tmp_path: Path) -> None:
    for phase in ("dns", "bind"):
        result = run(fake_az, tmp_path, phase, FAKE_NO_WEB_APP="1")
        assert result.returncode == 1, phase
        assert "not deployed" in result.stderr
    assert gddy_calls(fake_az) == []


def test_dns_dry_run_shows_the_dry_run_of_each_missing_record_and_adds_nothing(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "dns")
    assert result.returncode == 0, result.stderr
    assert real_adds(fake_az) == []
    dry = [c for c in adds(fake_az) if "--dry-run" in c]
    assert len(dry) == 2
    assert f"--type CNAME --name blog-studio --data {FQDN} --ttl 3600" in dry[0]
    assert f"--type TXT --name asuid.blog-studio --data {VERIFY} --ttl 3600" in dry[1]
    assert "Dry run" in result.stdout


def test_dns_apply_adds_both_records_after_their_dry_runs_and_reads_them_back(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "dns", "--apply")
    assert result.returncode == 0, result.stderr
    assert len(real_adds(fake_az)) == 2
    sequence = [("dry" if "--dry-run" in c else "real") for c in adds(fake_az)]
    assert sequence == ["dry", "real", "dry", "real"]
    assert "bind-domain.sh bind" in result.stdout


def test_dns_apply_fails_loudly_when_a_record_is_not_listed_afterwards(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "dns", "--apply", FAKE_GDDY_IGNORE_ADD="1")
    assert result.returncode == 1
    assert "not listed" in result.stderr


def test_dns_leaves_present_records_alone(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path, "dns", "--apply", FAKE_GDDY_RECORDS=BOTH)
    assert result.returncode == 0, result.stderr
    assert adds(fake_az) == []
    assert result.stdout.count("present") == 2


def test_dns_never_overwrites_a_cname_that_points_elsewhere(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    other = "CNAME|blog-studio|other.example.test"
    result = run(fake_az, tmp_path, "dns", "--apply", FAKE_GDDY_RECORDS=other)
    assert result.returncode == 1
    assert "other.example.test" in result.stderr
    assert adds(fake_az) == []


def test_bind_stops_while_dns_is_not_ready(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path, "bind", "--apply")
    assert result.returncode == 1
    assert "DNS not ready" in result.stderr
    assert FQDN in result.stderr and VERIFY in result.stderr
    assert writes(fake_az) == [] and env_text(tmp_path) == ""


def test_bind_dry_run_prints_the_commands_and_changes_nothing(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "bind", **READY)
    assert result.returncode == 0, result.stderr
    assert f"+ az containerapp hostname add --hostname {HOST}" in result.stdout
    assert "--validation-method CNAME" in result.stdout
    assert writes(fake_az) == [] and env_text(tmp_path) == ""


def test_bind_apply_adds_the_host_binds_a_managed_certificate_and_records_it(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(
        fake_az,
        tmp_path,
        "bind",
        "--apply",
        FAKE_CERT_STATES="Pending,Succeeded",
        **READY,
    )
    assert result.returncode == 0, result.stderr
    add, bind = writes(fake_az)
    assert add.startswith("containerapp hostname add") and f"--hostname {HOST}" in add
    assert "-n ca-blogstudio-web" in add and "-g rg-chatbot" in add
    assert "-o none" in add
    assert "--environment cae-blogstudio" in bind
    assert "--validation-method CNAME" in bind and "-o none" in bind
    text = env_text(tmp_path)
    assert f"BLOG_WEB_CUSTOM_DOMAIN={HOST}" in text
    assert f"BLOG_WEB_CERTIFICATE_NAME={CERT}" in text
    assert oct((tmp_path / ".env").stat().st_mode & 0o777) == "0o600"
    assert "deploy.sh" in result.stdout


def test_bind_writes_nothing_when_the_certificate_fails(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(
        fake_az, tmp_path, "bind", "--apply", FAKE_CERT_STATES="Failed", **READY
    )
    assert result.returncode == 1
    assert "failed" in result.stderr and "CAA" in result.stderr
    assert env_text(tmp_path) == ""


def test_bind_writes_nothing_when_the_certificate_is_never_issued(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(
        fake_az, tmp_path, "bind", "--apply", FAKE_CERT_STATES="Pending", **READY
    )
    assert result.returncode == 1
    assert "3 tries" in result.stderr
    assert env_text(tmp_path) == ""


def test_bind_writes_nothing_when_the_binding_is_not_sni(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "bind", "--apply", FAKE_BINDING="Disabled", **READY)
    assert result.returncode == 1
    assert "SNI" in result.stderr
    assert env_text(tmp_path) == ""


def test_a_second_bind_changes_nothing_in_azure(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(
        fake_az, tmp_path, "bind", "--apply", FAKE_CUSTOM_DOMAINS=HOST, **READY
    )
    assert result.returncode == 0, result.stderr
    assert "already bound" in result.stdout
    assert writes(fake_az) == []
    assert f"BLOG_WEB_CERTIFICATE_NAME={CERT}" in env_text(tmp_path)
