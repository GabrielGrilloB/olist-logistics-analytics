-- Uma linha por pedido. Todas as tabelas raw preservam os CSVs como texto.
CREATE TABLE analytics_orders AS
WITH ranked_reviews AS (
    SELECT *,
        COUNT(*) OVER (PARTITION BY order_id) AS review_count,
        ROW_NUMBER() OVER (
            PARTITION BY order_id
            ORDER BY TRY_CAST(review_answer_timestamp AS TIMESTAMP) DESC NULLS LAST,
                     TRY_CAST(review_creation_date AS TIMESTAMP) DESC NULLS LAST,
                     review_id DESC, review_score DESC,
                     review_comment_title DESC NULLS LAST,
                     review_comment_message DESC NULLS LAST
        ) AS position
    FROM raw_reviews
), typed AS (
    SELECT o.order_id, o.customer_id, c.customer_unique_id,
        c.customer_state, o.order_status,
        TRY_CAST(o.order_purchase_timestamp AS TIMESTAMP) AS purchased_at,
        TRY_CAST(o.order_delivered_customer_date AS TIMESTAMP) AS delivered_at,
        TRY_CAST(o.order_estimated_delivery_date AS TIMESTAMP) AS estimated_delivery_at,
        TRY_CAST(r.review_score AS INTEGER) AS review_score,
        COALESCE(r.review_count, 0) AS review_count
    FROM raw_orders o
    LEFT JOIN raw_customers c USING (customer_id)
    LEFT JOIN ranked_reviews r ON o.order_id = r.order_id AND r.position = 1
), flags AS (
    SELECT *,
        order_status = 'delivered'
        AND purchased_at IS NOT NULL AND delivered_at IS NOT NULL
        AND estimated_delivery_at IS NOT NULL
        AND delivered_at >= purchased_at
        AND estimated_delivery_at::DATE >= purchased_at::DATE AS delivery_eligible
    FROM typed
)
SELECT *, purchased_at::DATE AS purchase_date,
    delivered_at::DATE AS delivered_date,
    estimated_delivery_at::DATE AS estimated_delivery_date,
    CASE WHEN delivery_eligible
         THEN delivered_at::DATE > estimated_delivery_at::DATE END AS is_late,
    CASE WHEN delivery_eligible
         THEN GREATEST(DATE_DIFF('day', estimated_delivery_at::DATE, delivered_at::DATE), 0)
    END AS delay_days,
    CASE WHEN review_score BETWEEN 1 AND 5 THEN review_score <= 2 END AS is_low_review
FROM flags;

CREATE TABLE reconciliation AS
SELECT DATE_TRUNC('month', purchased_at)::DATE AS purchase_month,
    customer_state,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE delivery_eligible) AS eligible_orders,
    COUNT(*) FILTER (WHERE is_late) AS late_orders,
    COUNT(*) FILTER (WHERE delivery_eligible AND review_score BETWEEN 1 AND 5) AS reviewed_eligible_orders,
    COUNT(*) FILTER (WHERE delivery_eligible AND is_low_review) AS low_review_orders,
    COUNT(*) FILTER (WHERE is_late)::DOUBLE
        / NULLIF(COUNT(*) FILTER (WHERE delivery_eligible), 0) AS late_rate
FROM analytics_orders
GROUP BY 1, 2;
