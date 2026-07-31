# Modelo de Score

## Score atual

O Runner V2 calcula um score de descoberta com componentes de sinais de dor, relevância para a consulta, engajamento, atualidade, categorias heurísticas e confiança.

## Significado permitido

Força heurística de um sinal público compatível com uma consulta.

## Significados proibidos

O score não representa mercado, disposição a pagar, receita, preço, custo, prazo, facilidade de aquisição ou adequação pessoal.

## Camadas separadas

- score de descoberta: dado derivado do Runner V2;
- rastreabilidade: completude da origem;
- personal fit: inferência por habilidades;
- prontidão do plano: preenchimento do contrato;
- evidência comercial: fatos registrados;
- decisão: responsabilidade humana.

## Baseline

Precision só é calculada sobre itens rotulados como válidos ou falsos positivos. Sem rótulos, a dashboard exibe “Sem baseline”.

## Versão

O score do Runner V2 permanece preservado nesta entrega. Ajustes de pesos dependem do dataset rotulado da Fase 2.
