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
4. ✅ Ajustar a dashboard.

## Baselines

```text
6ec754e
feat: add resilient source snapshot runner v2

da463a1
chore: professionalize repository foundation

03671096af075291e9842cd8839e7840823660c9
feat: add income-focused landing dashboard
```

## Fontes ativas

GitHub, Stack Overflow, Software Recommendations, Web Applications, Hacker News e DEV Community. Reddit permanece adiado.

## Estado técnico validado antes desta entrega

Runner V2, seis fontes, cache SQLite, snapshots, operação degradada, fallback, 140 testes, CI em Python 3.11 e 3.12, dashboard, smoke HTTP, push e Git limpo.

## Nova estrutura

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
- landing orientada à próxima decisão.

## Restrições preservadas

Runner V2 e `scripts/run_colab.py` não podem ser alterados sem defeito comprovado. SQLite, cache, logs, tokens e temporários não entram no Git.

## Próximo gate de produto

Criar baseline real por curadoria: rotular oportunidades válidas e falsos positivos, medir Precision@10 e analisar erros antes de ajustar matching ou pesos.
