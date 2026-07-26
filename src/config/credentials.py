from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable


SecretReader = Callable[[str], str | None]


def _read_colab_secret(name: str) -> str | None:
    try:
        from google.colab import userdata

        value = userdata.get(name)

        if value:
            return str(value).strip()

    except Exception:
        return None

    return None


def get_credential(
    name: str,
    *,
    required: bool = False,
    secret_reader: SecretReader | None = None,
) -> str | None:
    """
    Busca uma credencial primeiro nas variáveis de ambiente
    e depois nos Secrets do Google Colab.
    """
    environment_value = os.getenv(name)

    if environment_value:
        value = environment_value.strip()

        if value:
            return value

    reader = secret_reader or _read_colab_secret
    secret_value = reader(name)

    if secret_value:
        value = str(secret_value).strip()

        if value:
            return value

    if required:
        raise RuntimeError(
            f"Credencial obrigatória não encontrada: {name}"
        )

    return None


@dataclass(frozen=True)
class Credentials:
    github_token: str | None
    producthunt_api_key: str | None
    producthunt_api_secret: str | None

    @classmethod
    def load(
        cls,
        *,
        require_github: bool = False,
        require_producthunt: bool = False,
        secret_reader: SecretReader | None = None,
    ) -> "Credentials":
        github_token = get_credential(
            "GITHUB_TOKEN",
            required=require_github,
            secret_reader=secret_reader,
        )

        producthunt_api_key = get_credential(
            "PRODUCTHUNT_API_KEY",
            required=require_producthunt,
            secret_reader=secret_reader,
        )

        producthunt_api_secret = get_credential(
            "PRODUCTHUNT_API_SECRET",
            required=require_producthunt,
            secret_reader=secret_reader,
        )

        return cls(
            github_token=github_token,
            producthunt_api_key=producthunt_api_key,
            producthunt_api_secret=producthunt_api_secret,
        )


credentials = Credentials.load()
