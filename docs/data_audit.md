# Auditoria dos dados Olist

Relatório gerado por `python src/build_analytics.py`.

| Arquivo | Linhas | Duplicatas exatas | Campos vazios |
|---|---:|---:|---:|
| customers | 99441 | 0 | 0 |
| geolocation | 1000163 | 261831 | 0 |
| items | 112650 | 0 | 0 |
| payments | 103886 | 0 | 0 |
| reviews | 99224 | 0 | 145903 |
| orders | 99441 | 0 | 4908 |
| products | 32951 | 0 | 2448 |
| sellers | 3095 | 0 | 0 |
| categories | 71 | 0 | 0 |

## Integridade referencial

- `orders.customer_id -> customers.customer_id` tem 0 referências ausentes.
- `items.order_id -> orders.order_id` tem 0 referências ausentes.
- `items.product_id -> products.product_id` tem 0 referências ausentes.
- `items.seller_id -> sellers.seller_id` tem 0 referências ausentes.
- `payments.order_id -> orders.order_id` tem 0 referências ausentes.
- `reviews.order_id -> orders.order_id` tem 0 referências ausentes.
- `products.product_category_name -> categories.product_category_name` tem 13 referências ausentes.

## Resultado validado

- `orders` = 99441
- `eligible_orders` = 96470
- `late_orders` = 6534
- `late_rate` = 0.06773090079817559
- `orders_with_multiple_reviews` = 547
- `orders_without_review` = 768
- `delivered_missing_delivery_date` = 8
- `delivery_before_purchase` = 0
- `estimate_before_purchase_day` = 0

## Tratamento

- Os nove arquivos originais são preservados. As duplicatas de geolocalização são registradas e essa tabela fica fora do cruzamento por pedido.
- Comentários vazios são permitidos. Nota ausente fica nula e a cobertura das avaliações deve acompanhar as comparações.
- Traduções de categoria ausentes são documentadas. Clientes e pedidos com chaves inválidas bloqueiam a publicação.
- Pedidos sem datas válidas ou com cronologia inconsistente permanecem na tabela e ficam fora do denominador de atraso.
- A data prometida é interpretada como um dia de calendário. Uma entrega no mesmo dia é pontual, independentemente do horário.
- Entre múltiplas avaliações, escolhe-se a resposta mais recente. Os critérios de desempate estão no SQL.
- Confira `audit.json` na versão local para as contagens por coluna e verificações de formato de datas.
