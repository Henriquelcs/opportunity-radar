# Arquitetura

## Contexto

O Opportunity Radar identifica dores públicas e gera oportunidades candidatas sem multiplicar chamadas externas para cada variação.

## Componentes

### Coletores

Consultam GitHub, Stack Overflow, Software Recommendations, Web Applications, Hacker News e DEV Community.

### Cache

`src/cache` mantém itens, snapshots, cooldowns e metadados de sincronização em SQLite não versionado.

### Runner V2

`src/operations/runner_v2.py` executa:

1. migração idempotente;
2. sincronização única por fonte;
3. fallback para cache;
4. expansão de consultas;
5. matching local;
6. scoring;
7. deduplicação;
8. persistência;
9. consolidação do status.

### Dashboard

Apresenta visão consolidada, oportunidades, curadoria, variações, execuções e inventário técnico.

## Fluxo

```text
Fonte pública
    ↓ uma vez por ciclo
Coletor resiliente
    ↓
Snapshot SQLite
    ↓ reutilizado
Consultas e variações locais
    ↓
Qualificação e score
    ↓
Deduplicação
    ↓
Banco operacional
    ↓
Dashboard
```

## Estados

- `SUCCESS`: fontes responderam com snapshot utilizável.
- `DEGRADED`: existe cache ou dados válidos apesar de falhas.
- `FAILED`: não existem dados suficientes.
- `PARTIAL_SUCCESS`: aceito quando há resultado válido em operação degradada.

## Resiliência

- respeito a `Retry-After`;
- cooldown em HTTP 429;
- isolamento por fonte;
- ausência de retry do pipeline inteiro;
- DEV sem detalhes individuais em massa;
- Hacker News com reutilização;
- dashboard disponível em estado degradado.

## Limites atuais

- matching e score precisam de refinamento;
- tradução pertence à etapa 4;
- indicadores ainda misturam histórico legado;
- quick tunnel não possui garantia de disponibilidade.
