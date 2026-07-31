# Operação no Google Colab

## Uso diário

```bash
python scripts/run_colab.py --mode all
```

## Modos

```bash
python scripts/run_colab.py --mode setup
python scripts/run_colab.py --mode verify
python scripts/run_colab.py --mode collect
python scripts/run_colab.py --mode dashboard
python scripts/run_colab.py --mode all
```

## Segredos

`GITHUB_TOKEN`, `GH_TOKEN` ou `GITHUB_PAT`; `DEVTO_API_KEY` e `STACKEXCHANGE_KEY` são opcionais. Não cole segredos em células.

## Bancos

```text
data/opportunity_radar_operational.db
data/source_cache.db
data/opportunity_radar_curation.db
data/opportunity_radar_product.db
```

Todos são artefatos operacionais e permanecem fora do Git.

## Persistência

O GitHub preserva código. Bancos do runtime do Colab precisam ser copiados para armazenamento persistente quando Henrique quiser mantê-los entre sessões.

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

Processos usam PID. Não use `pkill -f`.
