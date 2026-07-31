# Changelog

## Unreleased

### Landing e navegação

- títulos de oportunidades agora abrem detalhes dentro da landing;
- botão `Ver oportunidade` disponível em cada card;
- painel com conteúdo original, fonte, score, personal fit, rastreabilidade e hipóteses;
- ações claras para abrir a publicação e trabalhar na oportunidade;
- destaque visual da oportunidade selecionada;
- texto técnico legado removido da área visível;
- versão e commit exibidos discretamente no rodapé;
- argumentos visuais atualizados para a API atual do Streamlit;
- teste de regressão para navegação e chaves únicas.

### Produto

- definição oficial orientada até possível primeira receita;
- separação entre dado, evidência, inferência, hipótese e decisão;
- ciclo de vida e workspace de validação;
- personal fit e métricas de qualidade;
- registro de evidências, preço, custo, horas e receita;
- tradução preservando original.

### Dashboard

- landing orientada à próxima decisão;
- novas áreas Decisão, Validação e Métricas;
- áreas operacionais preservadas.

### Engenharia

- camada `src/product` isolada do Runner V2;
- banco de produto SQLite não versionado;
- testes de contrato, avaliação e persistência.

## Landing Dashboard V1 — 2026-07-27

- foco em renda extra;
- cards e resumo operacional.

## Runner V2 — 2026-07-26

- sincronização única por fonte;
- snapshots SQLite;
- classificação local;
- fallback para cache;
- operação degradada;
- bootstrap do Colab;
- Streamlit e Cloudflare Tunnel.

Commit de referência: `6ec754e`.
