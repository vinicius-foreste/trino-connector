# Dicionario de Campos

## Base Gold (receita)

1. advertiser_id: id do anunciante.
2. mes_base: mes de competencia do faturamento.
3. pacote: nome comercial do plano.
4. canal_conta: canal comercial (Inside, Field, Online, ND).
5. classificacao: Novo, Flat, Upgrade, Downgrade.
6. classificacao_churn: indicador de churn.
7. faturado_mes: valor principal de faturamento.
8. faturado_sva: valor de SVA no mes.
9. total_pago_sva: parte paga de SVA.

## Base Paids

1. base_month: mes de competencia do pagamento.
2. payment_month: mes de caixa (quando pagou).
3. payment_price: valor pago CB.
4. status_pagamento: Paid, Atrasado, Parcial.
5. dt: data tecnica de carga/particao (nao usar como chave de negocio).

## Base Planos

1. id_conta_olx: chave do anunciante (equivale a advertiser_id).
2. competencia: mes de competencia do plano.
3. valor_mensal: valor do plano no mes.
4. periodicidade: frequencia de cobranca.
5. status_recorrente: Novo, Flat, Upgrade, Churn.
6. package_name: nome do pacote.
7. tamanho: P, M, G.
8. channel: canal associado ao plano.

## Base Unificada

1. mes_ref: mes de competencia usado no dashboard.
2. receita_total: faturado_mes + faturado_sva.
3. pago_cb: valor pago vindo da Paids (por competencia).
4. gap_pago: faturado_mes - pago_cb.
5. flag_sem_pagamento: 1 quando nao houver match na paids.
6. flag_sem_plano: 1 quando nao houver match na planos.
