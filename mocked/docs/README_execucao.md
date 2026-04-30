# Guia de Execucao

## 1. Montar no Tableau (caminho rapido)

1. Abra Tableau Desktop.
2. Conecte arquivo de texto: `data/re_unified_tableau_2026.csv`.
3. Garanta tipos corretos:
   - `mes_ref`: date
   - campos de valor: number (decimal)
   - ids e dimensoes: string
4. Crie calculos:
   - `receita_total_calc = [faturado_mes] + [faturado_sva]`
   - `gap_pago_calc = [faturado_mes] - [pago_cb]`
   - `perc_pago_calc = IF [faturado_mes] = 0 THEN 0 ELSE [pago_cb] / [faturado_mes] END`
5. Monte visuais:
   - 4 cards KPI
   - 1 linha por `mes_ref` x `receita_total`
   - 1 barra por `canal_conta`
   - 1 barra por `pacote`
   - 1 tabela de conferencia por `advertiser_id`
6. Adicione filtros globais:
   - `mes_ref`
   - `pacote`
   - `canal_conta`

## 2. Caminho de estudo (relacionamentos)

1. Conecte tambem:
   - `re_gold_receita_unificado_air_2026.csv`
   - `re_silver_receita_cb_paids_air_2026.csv`
   - `re_silver_planos_periodicos_cb_2026.csv`
2. Relacionamentos:
   - Gold x Paids: `advertiser_id = advertiser_id` e `mes_base = base_month`
   - Gold x Planos: `advertiser_id = id_conta_olx` e `mes_base = competencia`
3. Compare os totais com a base unificada.

## 3. Resultado esperado

1. Dashboard unico com leitura executiva.
2. Consistencia de totais apos filtros.
3. Entendimento de competencia vs caixa.
