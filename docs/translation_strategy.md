# Estratégia de Tradução

## Princípio

O conteúdo original é imutável. Tradução é uma camada separada.

## Campos iniciais

Título e, futuramente, descrição. URLs, IDs, nomes próprios, código, comandos e mensagens técnicas devem permanecer intactos.

## Persistência

Cada tradução armazena hash do original, idioma de origem, idioma-alvo, provedor, modelo e data.

## Cache

A tradução é reutilizada enquanto o hash do original não mudar.

## Estado atual

A estrutura e a alternância original/tradução estão implementadas. Nesta fase, a tradução é manual; nenhum provedor externo foi escolhido.
