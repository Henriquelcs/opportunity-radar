# 📡 Opportunity Radar

[![CI](https://github.com/Henriquelcs/opportunity-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/Henriquelcs/opportunity-radar/actions/workflows/ci.yml)

Sistema para transformar dores públicas encontradas em comunidades técnicas em oportunidades de solução com inteligência artificial e potencial de renda extra.

## Objetivo

```text
Dores públicas
→ coleta resiliente
→ snapshot persistente
→ classificação local
→ oportunidades consolidadas
→ curadoria humana
```

O projeto consulta somente conteúdo público. Ele não publica respostas nem interage com usuários das fontes.

## Fontes integradas

| Fonte | Estado | Integração |
|---|---:|---|
| GitHub Issues | Ativa | Pesquisa de issues públicas |
| Stack Overflow | Ativa | Stack Exchange API |
| Software Recommendations | Ativa | Stack Exchange API |
| Web Applications | Ativa | Stack Exchange API |
| Hacker News | Ativa | Priorização de Ask HN |
| DEV Community | Ativa | API pública; chave opcional |
| Reddit | Adiada | OAuth e revisão de políticas |

## Arquitetura atual

```text
APIs públicas
    ↓
Coletores resilientes
    ↓
Cache e snapshots SQLite
    ↓
Runner V2
    ↓
Expansões processadas localmente
    ↓
Banco operacional SQLite
    ↓
Dashboard Streamlit
```

Características:

- cada fonte é sincronizada uma vez por ciclo;
- variações reutilizam o snapshot local;
- HTTP 429 respeita `Retry-After`;
- cache anterior mantém a operação disponível;
- falha isolada gera estado degradado;
- SQLite gerado não é versionado;
- dashboard abre durante operação degradada.

Consulte [Arquitetura](docs/architecture.md) e [ADR do Runner V2](docs/decisions/0001-source-snapshot-runner-v2.md).

## Google Colab

Uso diário:

```bash
python scripts/run_colab.py --mode all
```

Modos:

```bash
python scripts/run_colab.py --mode setup
python scripts/run_colab.py --mode verify
python scripts/run_colab.py --mode collect
python scripts/run_colab.py --mode dashboard
python scripts/run_colab.py --mode all
```

Consulte [Operação no Colab](docs/operations.md).

## Segredos

Configure no Colab Secrets:

| Nome | Obrigatório | Uso |
|---|---:|---|
| `GITHUB_TOKEN`, `GH_TOKEN` ou `GITHUB_PAT` | Para commit/push | GitHub |
| `DEVTO_API_KEY` | Não | DEV Community |
| `STACKEXCHANGE_KEY` | Não | Stack Exchange |

Nunca grave tokens em código, notebooks, bancos ou logs.

## Desenvolvimento local

Requisitos: Python 3.11 ou 3.12 e Git.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m compileall -q src scripts tests
python -m pytest -q
```

## Estrutura principal

```text
.github/workflows/       integração contínua
data/                    dados gerados, não versionados
docs/                    arquitetura, operação e decisões
scripts/run_colab.py     entrada operacional
src/cache/               cache e snapshots
src/collectors/          coletores
src/operations/          Runner V2
src/dashboard/           dashboard e curadoria
tests/                   testes automatizados
```

## Roadmap

1. ✅ Integrar novas fontes.
2. ✅ Unificar a operação do Colab.
3. 🟡 Profissionalizar o repositório.
4. ⏳ Ajustar a dashboard.

Estado detalhado: [docs/project_state.md](docs/project_state.md).

## Dados e privacidade

- somente fontes públicas;
- SQLite e caches fora do Git;
- conteúdo original e URLs preservados;
- curadoria humana obrigatória;
- score automático não representa validação comercial definitiva.

## Contribuição e segurança

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [CHANGELOG.md](CHANGELOG.md)

## Licenciamento

O projeto ainda não possui licença de reutilização definida. Até que uma licença seja adicionada, o código permanece protegido pelos direitos autorais do autor.
