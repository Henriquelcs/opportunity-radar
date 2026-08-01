# Estado do Projeto

## Produto

**Nome:** Opportunity Radar.

**Responsável e usuário principal:** Henrique Luiz Costa da Silva.

**Definição:** sistema pessoal de descoberta, priorização, validação e execução de oportunidades de renda extra.

**Fronteira aprovada:** acompanhar a oportunidade até decisão comercial, possível MVP e primeira receita, sem garantir resultado.

## Roadmap histórico preservado

1. ✅ Integrar novas fontes.
2. ✅ Unificar a operação do Colab.
3. ✅ Profissionalizar o repositório.
4. ✅ Ajustar a dashboard — criar Landing Dashboard V1.
5. ✅ Criar Product System V2.
6. ✅ Tornar oportunidades navegáveis na própria landing.
7. ✅ Simplificar a experiência — criar Product System V3.

## Baselines

```text
6ec754e
feat: add resilient source snapshot runner v2

da463a1
chore: professionalize repository foundation

03671096af075291e9842cd8839e7840823660c9
feat: add income-focused landing dashboard

6e0be6ac0b94a1f9dd7c50de8ae04ee59ca93498
feat: add personal validation and revenue system

9d2c9869dd7f6f167d459400046100577c6ba9ca
feat: make opportunity cards directly navigable
```

## Fontes ativas

GitHub, Stack Overflow, Software Recommendations, Web Applications, Hacker News e DEV Community. Reddit permanece adiado.

## Estado técnico validado antes desta entrega

Runner V2, seis fontes, cache SQLite, snapshots, operação degradada, fallback,
Product System V3, 154 testes locais, AppTest de cliques e estado e smoke HTTP
`200` com health `ok`. A validação remota ocorre no commit desta entrega.

## Estrutura atual

- contrato oficial do produto;
- glossário de conhecimento;
- score de descoberta separado de mercado;
- oportunidade qualificada e falso positivo;
- personal fit heurístico;
- workspace de validação;
- ciclo até primeira receita;
- evidências e eventos;
- preço, custo, horas e receita reais;
- tradução sem sobrescrever original;
- métricas de precision;
- jornada principal em Radar, Oportunidade e Validação;
- filtros avançados recolhidos;
- áreas técnicas em navegação secundária;
- cards navegáveis por callbacks, sem rerun explícito;
- painel de detalhes com conteúdo original;
- acesso direto à fonte e ao workspace de decisão;
- proteção `notranslate` nos elementos dinâmicos críticos;
- layout responsivo sem abas principais truncadas;
- AppTest real para abertura e preservação da seleção;
- versão e commit visíveis no rodapé.

## Contrato da melhoria visual

**Problema:** a landing apresentava muitas abas e ações concorrentes; ao clicar em
uma oportunidade, o rerun podia ocultar a mudança de estado e fazer o botão
parecer inoperante.

**Hipótese:** uma jornada persistente de três etapas reduz o atrito entre
descoberta, entendimento e validação.

**Evidência:** a oportunidade “How do I get Google forms edit url to work” foi encontrada, mas não estava acessível pelo título.

**Critério de aceite:** clicar no título ou em “Analisar oportunidade” muda para
a etapa Oportunidade, preserva a seleção e exibe conteúdo, fonte, score,
aderência, hipóteses e ações sem exceção.

**Métrica inicial:** dois AppTests reais cobrem abertura e início da validação.
Métricas de uso dependem de histórico real.

**Risco:** mutação do DOM por tradução automática ou regressão de estado entre
reruns do Streamlit.

**Rollback:** reverter apenas o commit visual. Runner V2, bancos, cache e coleta permanecem intactos.

## Restrições preservadas

Runner V2 e `scripts/run_colab.py` não podem ser alterados sem defeito comprovado. SQLite, cache, logs, tokens e temporários não entram no Git.

## Próximo gate de produto

Usar oportunidades reais para criar o primeiro baseline de curadoria: rotular válidas e falsos positivos, medir Precision@10 e analisar erros antes de ajustar matching ou pesos.
