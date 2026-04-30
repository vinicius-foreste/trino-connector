# Checklist QA

## Integridade de dados

1. [ ] Todos os meses de 2026 aparecem.
2. [ ] `receita_total = faturado_mes + faturado_sva` em todas as linhas.
3. [ ] Nao ha `advertiser_id` vazio.
4. [ ] Campos de valor estao como numero no Tableau.

## Integridade de visual

1. [ ] Filtro de data altera todos os graficos.
2. [ ] Filtro de pacote altera cards e graficos.
3. [ ] Filtro de canal altera cards e graficos.
4. [ ] Serie temporal esta em ordem cronologica.

## Integridade de negocio

1. [ ] `gap_pago` faz sentido (positivo quando pago menor que faturado).
2. [ ] Existem casos sem pagamento (pago_cb = 0) para teste.
3. [ ] Existem casos sem plano para teste de left join.
4. [ ] Top canais e top pacotes batem com tabela de conferencia.

## Preparacao para repasse

1. [ ] Print da tela geral.
2. [ ] Print com filtro aplicado.
3. [ ] Explicacao de 5 minutos preparada.
