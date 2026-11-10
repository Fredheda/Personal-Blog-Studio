from conftest import FakeAz

SCRIPT = "scripts/ci-azure-login.sh"
OIDC = {
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example.test/token",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-token",
    "AZURE_TENANT_ID": "tenant-1",
    "AZURE_SUBSCRIPTION_ID": "sub-1",
}


def test_it_exchanges_the_github_token_for_an_azure_session(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "client-1", env=OIDC)
    assert result.returncode == 0, result.stderr
    (curl,) = fake_az.curl_calls
    assert "audience=api://AzureADTokenExchange" in curl
    assert "https://oidc.example.test/token" in curl
    (login,) = [c for c in fake_az.calls if c.startswith("login")]
    assert "--service-principal -u client-1 -t tenant-1" in login
    assert "--federated-token fake-oidc-token" in login
    assert "account set --subscription sub-1" in fake_az.calls
    # The token is masked in the run log before az sees it.
    assert "::add-mask::fake-oidc-token" in result.stdout


def test_it_needs_the_oidc_environment(fake_az: FakeAz) -> None:
    env = {**OIDC, "ACTIONS_ID_TOKEN_REQUEST_URL": ""}
    result = fake_az.run(SCRIPT, "client-1", env=env)
    assert result.returncode == 1
    assert "id-token: write" in result.stderr
    assert fake_az.calls == []


def test_it_needs_the_tenant_and_the_subscription(fake_az: FakeAz) -> None:
    for name in ("AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID"):
        result = fake_az.run(SCRIPT, "client-1", env={**OIDC, name: ""})
        assert result.returncode != 0, name
    assert fake_az.calls == [] and fake_az.curl_calls == []
