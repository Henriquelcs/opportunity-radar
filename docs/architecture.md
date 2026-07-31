# Arquitetura

## Princípio

A coleta resiliente é separada da decisão de produto. O Runner V2 permanece responsável por dados públicos; a camada de produto registra interpretação, validação e resultado humano.

## Fluxo

```text
Fontes públicas
→ coletores resilientes
→ cache e snapshots SQLite
→ Runner V2
→ oportunidades candidatas
→ curadoria humana
→ avaliação de rastreabilidade e personal fit
→ workspace de validação
→ evidências e eventos comerciais
→ decisão, MVP e possível primeira receita
```

## Componentes

### Runner V2

Sincronização única por fonte, fallback, expansão local, matching, score, deduplicação e persistência. Não foi alterado nesta fase.

### Dashboard

Apresenta landing, decisão, validação, oportunidades, curadoria, métricas, consultas, execuções e área técnica.

### Camada de produto

`src/product/contracts.py` define conceitos e estados.

`src/product/assessment.py` produz inferências rastreáveis sem converter hipóteses em fatos.

`src/product/store.py` persiste workspaces, evidências, eventos e traduções em SQLite local não versionado.

## Bancos

- operacional: saída do Runner V2;
- cache: snapshots;
- curadoria: rótulos humanos;
- produto: validação, eventos e tradução.

## Rollback

A camada de produto pode ser revertida sem alterar o Runner V2 ou os bancos operacionais. O banco de produto é isolado.
