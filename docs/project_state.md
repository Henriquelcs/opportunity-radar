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
```

## Fontes ativas

GitHub, Stack Overflow, Software Recommendations, Web Applications, Hacker News e DEV Community. Reddit permanece adiado.

## Estado técnico validado antes desta entrega

Runner V2, seis fontes, cache SQLite, snapshots, operação degradada, fallback, 150 testes, CI em Python 3.11 e 3.12, Product System V2, smoke HTTP, push e Git limpo.

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
- landing orientada à próxima decisão;
- cards navegáveis;
- painel de detalhes com conteúdo original;
- acesso direto à fonte e ao workspace de decisão;
- versão e commit visíveis no rodapé.

## Contrato da melhoria visual

**Problema:** Henrique encontrava uma oportunidade na landing, mas não conseguia abrir seus detalhes diretamente pelo título.

**Hipótese:** navegação direta reduz atrito entre descoberta e análise.

**Evidência:** a oportunidade “How do I get Google forms edit url to work” foi encontrada, mas não estava acessível pelo título.

**Critério de aceite:** clicar no título ou em “Ver oportunidade” abre conteúdo, fonte, score, aderência, hipóteses e ações.

**Métrica inicial:** sucesso funcional da navegação e ausência de exceções no AppTest. Métricas de uso dependem de histórico real.

**Risco:** duplicação de widgets entre abas.

**Rollback:** reverter apenas o commit visual. Runner V2, bancos, cache e coleta permanecem intactos.

## Restrições preservadas

Runner V2 e `scripts/run_colab.py` não podem ser alterados sem defeito comprovado. SQLite, cache, logs, tokens e temporários não entram no Git.

## Próximo gate de produto

Usar oportunidades reais para criar o primeiro baseline de curadoria: rotular válidas e falsos positivos, medir Precision@10 e analisar erros antes de ajustar matching ou pesos.
