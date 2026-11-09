-- 1. Check identifier uniqueness.
USE hm_analysis;

SELECT
    'articles' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(article_id) AS non_null_ids,
    COUNT(DISTINCT article_id) AS unique_ids
FROM articles

UNION ALL

SELECT
    'customers',
    COUNT(*),
    COUNT(customer_id),
    COUNT(DISTINCT customer_id)
FROM customers;

-- 2. Check blank identifiers.
SELECT 
	'articles' AS table_name,
    COUNT(*) AS empty_ids
FROM articles
WHERE TRIM(article_id)=''

UNION ALL
SELECT
    'customers',
    COUNT(*)
FROM customers
WHERE TRIM(customer_id)='';

-- 3. Check transaction-to-dimension referential integrity.
SELECT
    COUNT(*) AS total_transactions,
    SUM(c.customer_id IS NULL) AS unmatched_customers,
    SUM(a.article_id IS NULL) AS unmatched_articles
FROM transactions_train AS t
LEFT JOIN customers AS c
    ON t.customer_id = c.customer_id
LEFT JOIN articles AS a
    ON t.article_id = a.article_id;

-- 4. Check dates and prices: missing values, date range, zero/negative prices, and price range.
SELECT 
	COUNT(*) AS total_row,
	SUM(t_dat IS NULL) AS miss_date,
    MIN(t_dat) AS first_date,
    MAX(t_dat) AS last_date,
    SUM(price IS NULL) AS miss_price,
    SUM(price=0) AS zero_price,
    SUM(price<0) AS negative_price,
    MAX(price) AS max_price,
    MIN(price) AS min_price
FROM transactions_train;

-- 5. Check missing ages and age range.
SELECT 
	COUNT(*) AS total_row,
    SUM(age IS NULL) AS miss_age,
    MIN(age) AS min_age,
    MAX(age) AS max_age,
    SUM(age<=0) AS to_review
FROM customers;

-- 6. Check daily date coverage.
SELECT
	MIN(t_dat) AS first_date,
    MAX(t_dat) AS last_date,
    DATEDIFF(MAX(t_dat),MIN(t_dat)) +1 AS expected_days,
    COUNT(DISTINCT t_dat) AS days_with_transactions
FROM transactions_train;

-- 7. Check sales-channel codes and purchasing activity.
SELECT
    sales_channel_id,
    COUNT(*) AS purchase_records,
    COUNT(DISTINCT customer_id) AS purchasing_customers
FROM transactions_train
GROUP BY sales_channel_id
ORDER BY sales_channel_id;