-- Task 4: customer repeat-purchase analysis.

-- 0. Record the data cutoff date.
USE hm_analysis;

SELECT MAX(t_dat)
INTO @data_end
FROM transactions_train;

-- 1. Customers purchasing on one day versus multiple distinct days.
WITH cnt_multi AS (
	SELECT
		customer_id,
		COUNT(DISTINCT t_dat) AS diff_date,
        (CASE WHEN COUNT(DISTINCT t_dat)=1 THEN 'once' ELSE 'multiple' END) AS class
		FROM transactions_train
        GROUP BY customer_id)
SELECT class, COUNT(*) AS customers,
       ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM cnt_multi
GROUP BY class

UNION ALL 

SELECT 'total', COUNT(*), 100.00
FROM cnt_multi;

-- 2. Time from the first to the second observed purchase day.
WITH first_buy AS (
    SELECT customer_id, MIN(t_dat) AS first_date
    FROM transactions_train
    GROUP BY customer_id
),
second_buy AS (
    SELECT f.customer_id, f.first_date, MIN(t.t_dat) AS second_date
    FROM first_buy f
    JOIN transactions_train t
      ON t.customer_id = f.customer_id
     AND t.t_dat > f.first_date
    GROUP BY f.customer_id, f.first_date
),
ranked_intervals AS (
    SELECT
        customer_id,
        DATEDIFF(second_date, first_date) AS gap_days,
        ROW_NUMBER() OVER (
            ORDER BY DATEDIFF(second_date, first_date), customer_id
        ) AS rn,
        COUNT(*) OVER () AS n
    FROM second_buy
)
SELECT
    COUNT(*) AS customers,
    ROUND(AVG(gap_days), 2) AS avg_days,
    ROUND(AVG(
        CASE
            WHEN rn IN (FLOOR((n + 1) / 2), FLOOR((n + 2) / 2))
            THEN gap_days
        END
    ), 2) AS median_days
FROM ranked_intervals;

-- 3. Second-purchase interval distribution for a bar chart.
WITH first_buy AS (
    SELECT customer_id, MIN(t_dat) AS first_date
    FROM transactions_train
    GROUP BY customer_id
),
second_buy AS (
    SELECT f.customer_id, f.first_date, MIN(t.t_dat) AS second_date
    FROM first_buy f
    JOIN transactions_train t
      ON t.customer_id = f.customer_id
     AND t.t_dat > f.first_date
    GROUP BY f.customer_id, f.first_date
)
SELECT
    CASE
        WHEN DATEDIFF(second_date, first_date) <= 7 THEN '01. 1–7天'
        WHEN DATEDIFF(second_date, first_date) <= 14 THEN '02. 8–14天'
        WHEN DATEDIFF(second_date, first_date) <= 30 THEN '03. 15–30天'
        WHEN DATEDIFF(second_date, first_date) <= 60 THEN '04. 31–60天'
        WHEN DATEDIFF(second_date, first_date) <= 90 THEN '05. 61–90天'
        WHEN DATEDIFF(second_date, first_date) <= 180 THEN '06. 91–180天'
        ELSE '07. 181天及以上'
    END AS interval_group,
    COUNT(*) AS customers,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS customer_pct
FROM second_buy
GROUP BY interval_group
ORDER BY interval_group;

-- 4. Build the temporary customer-level analysis table.
DROP TEMPORARY TABLE IF EXISTS customer_base;

CREATE TEMPORARY TABLE customer_base AS
WITH first_buy AS (
	SELECT customer_id,MIN(t_dat) AS first_date
    FROM transactions_train
    GROUP BY customer_id
),
first_day_sales AS (
	SELECT 
		t.customer_id,
        t.sales_channel_id,
        a.product_group_name,
        SUM(t.price) AS sales,
        ROW_NUMBER() OVER(
			PARTITION BY t.customer_id 
            ORDER BY SUM(t.price) DESC,t.sales_channel_id, a.product_group_name
        ) AS rn
	FROM transactions_train t
    JOIN first_buy f ON t.customer_id = f.customer_id AND t.t_dat = f.first_date
    JOIN articles a ON t.article_id = a.article_id
    GROUP BY t.customer_id, t.sales_channel_id, a.product_group_name
),
repeat_flag AS (
    SELECT 
        f.customer_id,
        MAX(DATEDIFF(t.t_dat, f.first_date) BETWEEN 1 AND 30)  AS repeat_30,
        MAX(DATEDIFF(t.t_dat, f.first_date) BETWEEN 1 AND 90)  AS repeat_90,
        MAX(DATEDIFF(t.t_dat, f.first_date) BETWEEN 1 AND 180) AS repeat_180
    FROM first_buy f
    JOIN transactions_train t ON t.customer_id = f.customer_id
    GROUP BY f.customer_id
)
SELECT 
    f.customer_id,
    f.first_date,
    s.sales_channel_id AS first_channel,
    s.product_group_name AS first_group,
    CASE 
        WHEN c.age IS NULL THEN 'unknown'
        WHEN c.age < 25 THEN '<25'
        WHEN c.age < 35 THEN '25-34'
        WHEN c.age < 45 THEN '35-44'
        WHEN c.age < 55 THEN '45-54'
        ELSE '55+'
    END AS age_group,
    r.repeat_30,
    r.repeat_90,
    r.repeat_180
FROM first_buy f
JOIN first_day_sales s ON s.customer_id = f.customer_id AND s.rn = 1
JOIN repeat_flag r     ON r.customer_id = f.customer_id
JOIN customers c       ON c.customer_id = f.customer_id;

-- 5. Check one row per customer and coverage of all purchasing customers.
SELECT
    COUNT(*) AS base_rows,
    COUNT(DISTINCT customer_id) AS base_customers,
    (SELECT COUNT(DISTINCT customer_id) FROM transactions_train)
        AS transaction_customers
FROM customer_base;

-- 6. Repeat-purchase rates within 30, 90, and 180 days.
SELECT
    COUNT(*) AS total_customers,

    SUM(first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY))
        AS eligible_customers_30d,

    SUM(first_date <= DATE_SUB(@data_end, INTERVAL 90 DAY))
        AS eligible_customers_90d,

    SUM(first_date <= DATE_SUB(@data_end, INTERVAL 180 DAY))
        AS eligible_customers_180d,

    ROUND(
        AVG(
            CASE
                WHEN first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY)
                THEN repeat_30
            END
        ) * 100, 2
    ) AS repeat_30d_pct,

    ROUND(
        AVG(
            CASE
                WHEN first_date <= DATE_SUB(@data_end, INTERVAL 90 DAY)
                THEN repeat_90
            END
        ) * 100, 2
    ) AS repeat_90d_pct,

    ROUND(
        AVG(
            CASE
                WHEN first_date <= DATE_SUB(@data_end, INTERVAL 180 DAY)
                THEN repeat_180
            END
        ) * 100, 2
    ) AS repeat_180d_pct

FROM customer_base;

-- 7. Repeat-purchase rates by first-observed purchase month.
SELECT
    DATE_FORMAT(first_date, '%Y-%m') AS first_purchase_month,
    COUNT(*) AS cohort_customers,

    SUM(first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY))
        AS eligible_customers_30d,

    SUM(first_date <= DATE_SUB(@data_end, INTERVAL 90 DAY))
        AS eligible_customers_90d,

    SUM(first_date <= DATE_SUB(@data_end, INTERVAL 180 DAY))
        AS eligible_customers_180d,

    ROUND(
        AVG(
            CASE
                WHEN first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY)
                THEN repeat_30
            END
        ) * 100, 2
    ) AS repeat_30d_pct,

    ROUND(
        AVG(
            CASE
                WHEN first_date <= DATE_SUB(@data_end, INTERVAL 90 DAY)
                THEN repeat_90
            END
        ) * 100, 2
    ) AS repeat_90d_pct,

    ROUND(
        AVG(
            CASE
                WHEN first_date <= DATE_SUB(@data_end, INTERVAL 180 DAY)
                THEN repeat_180
            END
        ) * 100, 2
    ) AS repeat_180d_pct

FROM customer_base
GROUP BY first_purchase_month
ORDER BY first_purchase_month;

-- 8. Thirty-day repeat purchase by first-purchase category.
SELECT
    first_group,
    COUNT(*) AS eligible_customers_30d,
    SUM(repeat_30) AS repeat_customers_30d,
    ROUND(AVG(repeat_30) * 100, 2) AS repeat_30d_pct
FROM customer_base
WHERE first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY)
GROUP BY first_group
ORDER BY repeat_30d_pct DESC, eligible_customers_30d DESC;

-- 9. Thirty-day repeat purchase by first-purchase channel.
SELECT
    first_channel,
    COUNT(*) AS eligible_customers_30d,
    SUM(repeat_30) AS repeat_customers_30d,
    ROUND(AVG(repeat_30) * 100, 2) AS repeat_30d_pct
FROM customer_base
WHERE first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY)
GROUP BY first_channel
ORDER BY repeat_30d_pct DESC, eligible_customers_30d DESC;

-- 10. Thirty-day repeat purchase by age group.
SELECT
    age_group,
    COUNT(*) AS eligible_customers_30d,
    SUM(repeat_30) AS repeat_customers_30d,
    ROUND(AVG(repeat_30) * 100, 2) AS repeat_30d_pct
FROM customer_base
WHERE first_date <= DATE_SUB(@data_end, INTERVAL 30 DAY)
GROUP BY age_group
ORDER BY repeat_30d_pct DESC, eligible_customers_30d DESC;

-- 11. Sales and unit contributions from subsequent purchase days.
SELECT
    CASE WHEN t.t_dat > b.first_date THEN 'existing' ELSE 'new' END AS customer_type,
    COUNT(*) AS units,
    SUM(t.price) AS sales,
    ROUND(COUNT(*) * 100 / SUM(COUNT(*)) OVER (), 2) AS units_pct,
    ROUND(SUM(t.price) * 100 / SUM(SUM(t.price)) OVER (), 2) AS sales_pct
FROM transactions_train t
JOIN customer_base b USING (customer_id)
GROUP BY customer_type;

-- 12. Check original transaction totals.
SELECT
    COUNT(*) AS transaction_units,
    SUM(price) AS transaction_sales
FROM transactions_train;
