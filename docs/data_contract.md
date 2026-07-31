# Contrato de Dados

## Banco operacional

Produzido pelo Runner V2. Contém oportunidades, matches, consultas, variações, sincronizações e execuções.

## Banco de curadoria

Contém classificação humana e notas por URL.

## Banco de produto

`opportunity_radar_product.db` contém:

- `product_workspaces`;
- `product_evidence`;
- `product_events`;
- `product_translations`.

## Regras

SQLite não é versionado. Conteúdo original e URL são preservados. Valores ausentes permanecem vazios. Receita, custo e horas só são preenchidos por evento real. Tradução não sobrescreve original.
