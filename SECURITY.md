# Segurança

## Escopo

O projeto consulta fontes públicas e armazena resultados localmente em SQLite.

## Relato responsável

Não abra issue pública contendo token, chave, credencial, dado pessoal, URL autenticada ou conteúdo privado. Use um canal privado do proprietário.

## Segredos suportados

- `GITHUB_TOKEN`, `GH_TOKEN` ou `GITHUB_PAT`;
- `DEVTO_API_KEY`;
- `STACKEXCHANGE_KEY`.

Segredos devem permanecer no Colab Secrets ou em variáveis de ambiente locais.

## Regras

- logs não imprimem valores de segredos;
- SQLite e caches não são versionados;
- token não fica salvo na URL do remoto;
- cabeçalhos sensíveis não entram em logs;
- falhas externas são isoladas por fonte.

## Dependências

A CI executa compilação e testes em Python 3.11 e 3.12.
