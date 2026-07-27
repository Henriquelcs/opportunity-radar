# Estado do Projeto

## Produto

**Nome:** Opportunity Radar

**Objetivo:** transformar dores públicas em oportunidades de solução com IA e potencial de renda extra.

**Responsável:** Henrique Luiz Costa da Silva.

## Roadmap

1. ✅ Integrar novas fontes.
2. ✅ Unificar a operação do Colab.
3. 🟡 Profissionalizar o repositório.
4. ⏳ Ajustar a dashboard.

## Fontes ativas

- GitHub;
- Stack Overflow;
- Software Recommendations;
- Web Applications;
- Hacker News;
- DEV Community.

Reddit permanece adiado.

## Runner V2

Baseline:

```text
6ec754e
feat: add resilient source snapshot runner v2
```

Evidências:

- 130 testes;
- smoke real;
- operação degradada aceita;
- cache por fonte;
- dashboard HTTP 200;
- commit e push;
- Git limpo.

## Operação

```bash
python scripts/run_colab.py --mode all
```

## Implementado

- cache SQLite persistente;
- coleta incremental;
- snapshot por fonte;
- cooldown e `Retry-After`;
- fallback para cache;
- DEV uma vez por ciclo;
- Hacker News com reuso;
- variações locais;
- operação degradada;
- processos por PID;
- Cloudflared fixado;
- bootstrap zerado.

## Pendências

Etapa 3:

- documentação;
- integração contínua;
- segurança;
- contribuição;
- decisões arquiteturais.

Etapa 4:

- separar estados das fontes;
- corrigir indicadores legados;
- tradução com cache;
- preservar e exibir original;
- melhorar matching e score;
- reforçar deduplicação.

## Continuidade

Não reconstruir o projeto. Partir deste arquivo e do commit mais recente confirmado.
