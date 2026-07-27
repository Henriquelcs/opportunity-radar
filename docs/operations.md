# Operação no Google Colab

## Uso diário

```bash
python scripts/run_colab.py --mode all
```

Em runtime zerado, o notebook clona ou atualiza o repositório, carrega segredos, executa o Runner V2 e abre a dashboard.

## Modos

```bash
python scripts/run_colab.py --mode setup
python scripts/run_colab.py --mode verify
python scripts/run_colab.py --mode collect
python scripts/run_colab.py --mode dashboard
python scripts/run_colab.py --mode all
```

## Segredos

- `GITHUB_TOKEN`, `GH_TOKEN` ou `GITHUB_PAT`;
- `DEVTO_API_KEY`, opcional;
- `STACKEXCHANGE_KEY`, opcional.

Não cole segredos em células.

## Bancos

```text
data/opportunity_radar_operational.db
data/source_cache.db
data/opportunity_radar_curation.db
```

SQLite é artefato operacional e não entra no Git.

## Operação degradada

É esperado que uma fonte utilize cache, solicite backoff ou retorne HTTP 429. A operação é válida quando existe snapshot, oportunidades são persistidas, a dashboard responde HTTP 200 e os status ficam registrados.

## Diagnóstico

```bash
git status --short
python scripts/run_colab.py --mode verify
```

Logs:

```text
/content/opportunity-radar-runtime/streamlit.log
/content/opportunity-radar-runtime/cloudflared.log
```

O runner usa PID. Não use `pkill -f`.

## Reinício

O GitHub preserva o código. Bancos do runtime só permanecem quando copiados para armazenamento persistente.
