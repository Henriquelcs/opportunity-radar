# ADR 0001 — Runner baseado em snapshots

- Status: Aceito
- Data: 2026-07-26

## Contexto

O runner anterior repetia todas as fontes para cada variação. HTTP 429 no DEV derrubava resultados válidos e o retry repetia o pipeline inteiro.

## Decisão

```text
sincronizar cada fonte uma vez
→ persistir snapshot
→ executar variações localmente
→ consolidar
→ atualizar dashboard
```

Cada fonte possui isolamento. Cache anterior é reutilizado quando uma API está indisponível.

## Consequências positivas

- menos chamadas;
- menor risco de rate limit;
- menor tempo;
- reutilização entre consultas;
- dashboard em estado degradado;
- rastreabilidade.

## Consequências negativas

- migrações SQLite exigem cuidado;
- snapshots podem ficar desatualizados;
- matching local precisa evoluir;
- cache precisará de retenção.

## Regras

- `PARTIAL_SUCCESS` com dados válidos é aceito;
- HTTP 429 não derruba o ciclo;
- `Retry-After` é respeitado;
- sem cache, apenas a fonte é ignorada;
- logs em tempo real;
- SQLite fora do Git;
- segredos fora do código.
