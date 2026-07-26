import pytest

from src.config.credentials import (
    Credentials,
    get_credential,
)


def test_environment_variable_has_priority(
    monkeypatch,
):
    monkeypatch.setenv(
        "GITHUB_TOKEN",
        "environment-token",
    )

    value = get_credential(
        "GITHUB_TOKEN",
        secret_reader=lambda _: "secret-token",
    )

    assert value == "environment-token"


def test_reads_secret_when_environment_is_empty(
    monkeypatch,
):
    monkeypatch.delenv(
        "GITHUB_TOKEN",
        raising=False,
    )

    value = get_credential(
        "GITHUB_TOKEN",
        secret_reader=lambda _: "secret-token",
    )

    assert value == "secret-token"


def test_required_credential_raises_error(
    monkeypatch,
):
    monkeypatch.delenv(
        "MISSING_CREDENTIAL",
        raising=False,
    )

    with pytest.raises(RuntimeError):
        get_credential(
            "MISSING_CREDENTIAL",
            required=True,
            secret_reader=lambda _: None,
        )


def test_credentials_loads_all_values(
    monkeypatch,
):
    monkeypatch.delenv(
        "GITHUB_TOKEN",
        raising=False,
    )
    monkeypatch.delenv(
        "PRODUCTHUNT_API_KEY",
        raising=False,
    )
    monkeypatch.delenv(
        "PRODUCTHUNT_API_SECRET",
        raising=False,
    )

    values = {
        "GITHUB_TOKEN": "github-token",
        "PRODUCTHUNT_API_KEY": "ph-key",
        "PRODUCTHUNT_API_SECRET": "ph-secret",
    }

    credentials = Credentials.load(
        secret_reader=values.get,
    )

    assert credentials.github_token == "github-token"
    assert credentials.producthunt_api_key == "ph-key"
    assert (
        credentials.producthunt_api_secret
        == "ph-secret"
    )
