-- 1. Monthly performance by channel.
WITH monthly AS (
    SELECT
        DATE_FORMAT(t_dat, '%Y-%m') AS month,
        sales_channel_id,
        COUNT(DISTINCT customer_id) AS customer_per_month,
        SUM(price) AS sale_per_month,
        SUM(price) / COUNT(DISTINCT customer_id) AS spend_per_customer,
        COUNT(*) AS units_sold,
        COUNT(*) / COUNT(DISTINCT customer_id) AS unit_per_customer
    FROM transactions_train
    GROUP BY month, sales_channel_id
)

SELECT
    month,
    sales_channel_id,

    sale_per_month,
    ROUND(
        (sale_per_month - LAG(sale_per_month) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        )) * 100
        / LAG(sale_per_month) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        ), 2
    ) AS month_growth_rate,

    customer_per_month,
    ROUND(
        (customer_per_month - LAG(customer_per_month) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        )) * 100
        / LAG(customer_per_month) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        ), 2
    ) AS customer_growth_rate,

    units_sold,
    unit_per_customer,
    ROUND(
        (unit_per_customer - LAG(unit_per_customer) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        )) * 100
        / LAG(unit_per_customer) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        ), 2
    ) AS unit_per_customer_growth_rate,

    spend_per_customer,
    ROUND(
        (spend_per_customer - LAG(spend_per_customer) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        )) * 100
        / LAG(spend_per_customer) OVER (
            PARTITION BY sales_channel_id ORDER BY month
        ), 2
    ) AS spend_per_customer_growth_rate,

    ROUND(
        sale_per_month * 100
        / SUM(sale_per_month) OVER (PARTITION BY month), 2
    ) AS sales_channel_share

FROM monthly
ORDER BY month, sales_channel_id;


-- 2. Monthly performance across all channels.
WITH monthly AS (
    SELECT
        DATE_FORMAT(t_dat, '%Y-%m') AS month,
        COUNT(DISTINCT customer_id) AS customer_per_month,
        SUM(price) AS sale_per_month,
        SUM(price) / COUNT(DISTINCT customer_id) AS spend_per_customer,
        COUNT(*) AS units_sold,
        COUNT(*) / COUNT(DISTINCT customer_id) AS unit_per_customer
    FROM transactions_train
    GROUP BY month
)

SELECT
    month,

    sale_per_month,
    ROUND(
        (sale_per_month - LAG(sale_per_month) OVER (
            ORDER BY month
        )) * 100
        / LAG(sale_per_month) OVER (
            ORDER BY month
        ), 2
    ) AS month_growth_rate,

    customer_per_month,
    ROUND(
        (customer_per_month - LAG(customer_per_month) OVER (
            ORDER BY month
        )) * 100
        / LAG(customer_per_month) OVER (
            ORDER BY month
        ), 2
    ) AS customer_growth_rate,

    units_sold,
    unit_per_customer,
    ROUND(
        (unit_per_customer - LAG(unit_per_customer) OVER (
            ORDER BY month
        )) * 100
        / LAG(unit_per_customer) OVER (
            ORDER BY month
        ), 2
    ) AS unit_per_customer_growth_rate,

    spend_per_customer,
    ROUND(
        (spend_per_customer - LAG(spend_per_customer) OVER (
            ORDER BY month
        )) * 100
        / LAG(spend_per_customer) OVER (
            ORDER BY month
        ), 2
    ) AS spend_per_customer_growth_rate

FROM monthly
ORDER BY month;
