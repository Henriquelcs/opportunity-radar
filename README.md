# 📡 Opportunity Radar

[![CI](https://github.com/Henriquelcs/opportunity-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/Henriquelcs/opportunity-radar/actions/workflows/ci.yml)

O **Opportunity Radar** é um sistema pessoal de descoberta, priorização, validação e execução de oportunidades de renda extra para **Henrique Luiz Costa da Silva**.

Ele coleta dores publicadas em fontes públicas, preserva o conteúdo original, organiza sinais e ajuda Henrique a escolher o menor teste possível antes de investir tempo e dinheiro.

## Problema resolvido

Ideias são abundantes. O risco está em escolher uma dor fraca, construir antes de validar, não encontrar comprador ou continuar investindo sem evidência.

```text
Dores públicas
→ sinais rastreáveis
→ curadoria humana
→ oportunidade qualificada
→ comprador identificado
→ menor teste possível
→ validação de interesse e preço
→ decisão de continuar ou descartar
→ plano de MVP
→ possível primeira receita
→ aprendizado registrado
```

O produto **não garante** mercado, disposição a pagar, faturamento ou receita. Ele reduz incerteza e torna decisões rastreáveis.

## Usuário principal

Henrique possui experiência com automações, APIs REST, Python, Google Colab, Apps Script, integrações, processos operacionais, suporte técnico, Streamlit, SQLite e ferramentas de IA. O sistema prioriza oportunidades compatíveis com essas capacidades, sem inventar tempo, orçamento ou acesso a compradores.

## O que entra na engine

Conteúdo público proveniente de:

| Fonte | Estado |
|---|---:|
| GitHub Issues | Ativa |
| Stack Overflow | Ativa |
| Software Recommendations | Ativa |
| Web Applications | Ativa |
| Hacker News | Ativa |
| DEV Community | Ativa |
| Reddit | Adiada |

## O que a engine faz

O Runner V2 sincroniza cada fonte uma vez por ciclo, persiste snapshots SQLite, reutiliza os dados nas variações, identifica sinais de dor, calcula o score de descoberta, remove duplicações operacionais e grava oportunidades candidatas.

```text
Fontes públicas
→ coletores resilientes
→ cache e snapshots SQLite
→ Runner V2
→ matching e score local
→ deduplicação
→ banco operacional
→ camada de produto
→ dashboard
```

## Score de descoberta

O score existente mede a **força heurística de um sinal público** com base em correspondência com consultas, sinais textuais de dor, engajamento e atualidade.

Ele não mede:

- tamanho de mercado;
- comprador;
- orçamento;
- disposição a pagar;
- custo real;
- prazo real;
- potencial de faturamento;
- probabilidade de primeira receita.

A dashboard separa score de descoberta, rastreabilidade, personal fit, prontidão do plano, evidência comercial e decisão humana.

## Oportunidade qualificada

Um item coletado nasce como **sinal**. Ele só é considerado oportunidade qualificada quando existe:

1. decisão humana de que não é falso positivo;
2. dor confirmada no ciclo de vida;
3. possível comprador identificado;
4. pelo menos uma evidência registrada que sustente a hipótese.

## Curadoria

A curadoria classifica sinais como pendentes, em análise, válidos ou falsos positivos. As decisões e seus motivos formam o dataset de avaliação usado para medir precision e calibrar o sistema.

## Dado, evidência e hipótese

- **Dado coletado:** conteúdo obtido diretamente da fonte.
- **Evidência:** dado que sustenta ou contradiz uma conclusão.
- **Inferência:** interpretação produzida pelo sistema.
- **Hipótese:** afirmação ainda não validada.
- **Estimativa:** aproximação com premissas declaradas.
- **Decisão humana:** escolha realizada por Henrique.

## Da oportunidade à renda

A camada de produto registra:

- usuário afetado e possível comprador;
- problema e hipótese de monetização;
- menor teste antes do desenvolvimento;
- canal de acesso;
- preço a testar;
- critérios de continuidade e descarte;
- evidências, entrevistas e contatos;
- custos e horas investidas;
- MVP;
- receita real, quando existir;
- aprendizados.

## Dashboard

A Product System V3 conduz a jornada em três etapas:

1. **Radar:** localizar e escolher um sinal público.
2. **Oportunidade:** ler o original e separar evidência, inferência e hipótese.
3. **Validação:** definir o menor teste e registrar fatos comerciais observáveis.

Busca e filtros avançados ficam na lateral. Curadoria, métricas, consultas,
execuções e inventário técnico permanecem disponíveis em uma área secundária,
sem competir com a jornada principal.

Os botões usam callbacks com estado persistente, a interface possui proteção
contra tradução automática nos elementos dinâmicos e o fluxo de clique é
validado com `streamlit.testing.v1.AppTest`.

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

## Bancos locais

```text
data/opportunity_radar_operational.db
data/source_cache.db
data/opportunity_radar_curation.db
data/opportunity_radar_product.db
```

Nenhum SQLite, cache, log, token ou arquivo temporário é versionado.

## Estrutura

```text
src/cache/          cache e snapshots
src/collectors/     fontes públicas
src/operations/     Runner V2 preservado
src/dashboard/      landing e áreas operacionais
src/product/        contrato, avaliação e ciclo de validação
docs/               decisões e contratos do produto
tests/              testes técnicos e de produto
```

## Limitações atuais

- o score ainda não possui baseline amplo de precision;
- personal fit é inferência heurística;
- comprador, preço e monetização dependem de validação humana;
- tradução automática não foi ativada; a estrutura preserva original e permite tradução manual;
- deduplicação semântica entre relatos diferentes ainda precisa evoluir;
- quick tunnel não possui garantia de disponibilidade.

## Diferenciação estratégica

O Opportunity Radar não pretende ser apenas um gerador de ideias. Ele foi desenhado para conduzir Henrique da descoberta à decisão comercial, evitando construção prematura e preservando o aprendizado de cada avanço ou descarte.

## Documentação

- [Definição do produto](docs/product_definition.md)
- [Score](docs/scoring_model.md)
- [Qualidade](docs/opportunity_quality.md)
- [Ciclo de vida](docs/opportunity_lifecycle.md)
- [Métricas](docs/product_metrics.md)
- [Roadmap](docs/roadmap.md)
- [Estado atual](docs/project_state.md)
- [Operação](docs/operations.md)
- [Arquitetura](docs/architecture.md)

## Segurança

Configure `GITHUB_TOKEN`, `GH_TOKEN` ou `GITHUB_PAT` no Colab Secrets. `DEVTO_API_KEY` e `STACKEXCHANGE_KEY` são opcionais. Nunca grave segredos no código ou nos bancos.
