-- SQL de referencia para unificar as 3 bases
-- Observacao: ajuste o FROM para seu ambiente (csv stage, tabela temporaria, etc.)

WITH gold AS (
  SELECT
    advertiser_id,
    DATE_TRUNC('month', mes_base) AS mes_ref,
    pacote,
    canal_conta,
    dono_conta,
    estado,
    municipio,
    classificacao,
    classificacao_churn,
    SUM(faturado_mes) AS faturado_mes,
    SUM(faturado_sva) AS faturado_sva,
    SUM(total_pago_sva) AS total_pago_sva
  FROM re_gold_receita_unificado_air_2026
  GROUP BY 1,2,3,4,5,6,7,8,9
),
paids AS (
  SELECT
    advertiser_id,
    DATE_TRUNC('month', base_month) AS mes_ref_competencia,
    DATE_TRUNC('month', payment_month) AS mes_ref_pagamento,
    SUM(payment_price) AS pago_cb
  FROM re_silver_receita_cb_paids_air_2026
  GROUP BY 1,2,3
),
planos AS (
  SELECT
    id_conta_olx AS advertiser_id,
    DATE_TRUNC('month', competencia) AS mes_ref,
    SUM(valor_mensal) AS valor_mensal,
    MAX(periodicidade) AS periodicidade,
    MAX(channel) AS channel_plano,
    MAX(status_recorrente) AS status_recorrente,
    MAX(package_name) AS package_name,
    MAX(tamanho) AS tamanho_plano,
    MAX(estado_conta) AS estado_conta,
    MAX(cidade_conta) AS cidade_conta
  FROM re_silver_planos_periodicos_cb_2026
  GROUP BY 1,2
)
SELECT
  g.advertiser_id,
  g.mes_ref,
  g.pacote,
  g.canal_conta,
  g.dono_conta,
  g.estado,
  g.municipio,
  g.classificacao,
  g.classificacao_churn,
  g.faturado_mes,
  g.faturado_sva,
  g.total_pago_sva,
  (g.faturado_mes + g.faturado_sva) AS receita_total,
  COALESCE(p.pago_cb, 0) AS pago_cb,
  (g.faturado_mes - COALESCE(p.pago_cb, 0)) AS gap_pago,
  CASE WHEN p.pago_cb IS NULL THEN 1 ELSE 0 END AS flag_sem_pagamento,
  COALESCE(pl.valor_mensal, 0) AS valor_mensal,
  pl.periodicidade,
  pl.channel_plano,
  pl.status_recorrente,
  pl.package_name,
  pl.tamanho_plano,
  pl.estado_conta,
  pl.cidade_conta,
  CASE WHEN pl.advertiser_id IS NULL THEN 1 ELSE 0 END AS flag_sem_plano,
  p.mes_ref_pagamento
FROM gold g
LEFT JOIN paids p
  ON g.advertiser_id = p.advertiser_id
 AND g.mes_ref = p.mes_ref_competencia
LEFT JOIN planos pl
  ON g.advertiser_id = pl.advertiser_id
 AND g.mes_ref = pl.mes_ref
ORDER BY g.mes_ref, g.advertiser_id;
