# Mocked Tableau RE Project

Objetivo: permitir que voce trabalhe no fim de semana com dados simulados (mock) e reproduza um dashboard no Tableau parecido com o cenario real.

## O que esta incluido

1. `data/` com 3 bases mockadas e 1 base unificada pronta para Tableau.
2. `sql/` com a logica de join entre as 3 bases.
3. `docs/` com guia de execucao, dicionario de campos e checklist de QA.
4. `study/` com trilha de estudo para nivel basico.

## Ordem sugerida (iniciante)

1. Comece por `data/re_unified_tableau_2026.csv`.
2. Monte o dashboard com os filtros `mes_ref`, `pacote` e `canal_conta`.
3. Depois estude os relacionamentos usando as 3 bases originais.

## Entrega minima para segunda-feira

1. 1 dashboard funcional no Tableau.
2. Filtros globais funcionando.
3. Cards: `receita_total`, `faturado_mes`, `faturado_sva`, `pago_cb`.
4. 1 serie temporal e 2 graficos de barras.
5. Checklist de QA marcado.

## Nota importante

Os dados sao mockados, mas com comportamento realista:

1. Competencia e pagamento podem cair em meses diferentes.
2. Existem registros sem match em paids/planos para simular producao.
3. O join correto deve preservar o grao da Gold (`advertiser_id + mes_base`).
