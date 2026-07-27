# Contribuindo

## Princípios

- O GitHub é a fonte oficial do código.
- Não versione SQLite, caches, logs, tokens ou arquivos temporários.
- Preserve conteúdo original e URLs das fontes.
- Falhas isoladas não devem derrubar toda a operação.
- Não altere a ordem do roadmap sem decisão explícita.

## Preparação

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

## Quality gate

```bash
python -m compileall -q src scripts tests
python -m pytest -q
git diff --check
git status --short
```

## Commits

Use mensagens objetivas:

```text
feat: adiciona capacidade
fix: corrige comportamento
test: amplia cobertura
docs: atualiza documentação
chore: manutenção estrutural
```

## Pull requests

Informe problema, solução, testes, evidências, riscos e rollback.

## Segredos

Nunca inclua tokens, chaves, cookies, credenciais OAuth, URLs autenticadas ou conteúdo do Colab Secrets.
