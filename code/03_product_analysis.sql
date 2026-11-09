-- Product and category analysis.
-- 1. Overall category structure: compare group/type sales and their shares within groups and overall.
SELECT 
	product_group_name,
    product_type_name,
    SUM(SUM(price)) OVER (PARTITION BY product_group_name) AS group_sale,
    SUM(SUM(price)) OVER (PARTITION BY product_group_name)*100/SUM(SUM(price)) OVER() AS group_sale_perc,
    SUM(price) AS type_sale,
    ROUND(SUM(price)*100/ SUM(SUM(price)) OVER (PARTITION BY product_group_name),2) AS type_sale_group_perc,
    ROUND(SUM(price)*100/ SUM(SUM(price)) OVER (),2) AS type_sale_total_perc

FROM transactions_train t
JOIN articles a USING(article_id)
GROUP BY product_group_name,product_type_name
ORDER BY group_sale DESC,type_sale DESC;

-- 2. Seasonal category structure: pool the same calendar seasons across years and compare sales mix.
WITH base AS (
    SELECT 
        CASE 
            WHEN MONTH(t.t_dat) IN (3,4,5)  THEN 'Spring'
            WHEN MONTH(t.t_dat) IN (6,7,8)  THEN 'Summer'
            WHEN MONTH(t.t_dat) IN (9,10,11) THEN 'Autumn'
            ELSE 'Winter'
        END AS season,
        product_group_name,
        product_type_name,
        SUM(price) AS type_sale
    FROM transactions_train t
    JOIN articles a USING (article_id)
    GROUP BY season, product_group_name, product_type_name
)
SELECT 
    season,
    product_group_name,
    product_type_name,
    type_sale,
    SUM(type_sale) OVER (PARTITION BY season, product_group_name) AS group_sale,
    ROUND(SUM(type_sale) OVER (PARTITION BY season, product_group_name) * 100
          / SUM(type_sale) OVER (PARTITION BY season), 2) AS group_pct_of_season,
    ROUND(type_sale * 100
          / SUM(type_sale) OVER (PARTITION BY season, product_group_name), 2) AS type_pct_of_group,
    ROUND(type_sale * 100
          / SUM(type_sale) OVER (PARTITION BY season), 2) AS type_pct_of_season
FROM base
ORDER BY FIELD(season, 'Spring', 'Summer', 'Autumn', 'Winter'), group_sale DESC, type_sale DESC;

-- 3. Monthly category structure: compare group/type sales and shares within each month.
SELECT 
	DATE_FORMAT(t_dat,'%Y-%m') AS month,
	product_group_name,
    product_type_name,
    SUM(SUM(price)) OVER (PARTITION BY DATE_FORMAT(t_dat,'%Y-%m'),product_group_name) AS group_sale,
    SUM(SUM(price)) OVER (PARTITION BY DATE_FORMAT(t_dat,'%Y-%m'),product_group_name)*100/SUM(SUM(price)) OVER(PARTITION BY DATE_FORMAT(t_dat,'%Y-%m')) AS group_sale_perc,
    SUM(price) AS type_sale,
    SUM(price)*100/ SUM(SUM(price)) OVER (PARTITION BY DATE_FORMAT(t_dat,'%Y-%m'),product_group_name) AS type_sale_group_perc,
    SUM(price)*100/ SUM(SUM(price)) OVER (PARTITION BY DATE_FORMAT(t_dat,'%Y-%m')) AS type_sale_total_perc

FROM transactions_train t
JOIN articles a USING(article_id)
GROUP BY month,product_group_name,product_type_name
ORDER BY month,group_sale DESC,type_sale DESC;

-- 4. Channel category structure: compare group/type sales mix within channels and overall contributions.
SELECT 
	sales_channel_id,
	product_group_name,
    product_type_name,
    SUM(price) AS type_sale,
    SUM(SUM(price)) OVER (PARTITION BY sales_channel_id,product_group_name) AS group_sale,
    ROUND(SUM(SUM(price)) OVER (PARTITION BY sales_channel_id,product_group_name)*100/SUM(SUM(price)) OVER(PARTITION BY sales_channel_id),2) AS group_sale_perc_of_channel,
    ROUND(SUM(price)*100/SUM(SUM(price))OVER (PARTITION BY sales_channel_id,product_group_name),2) AS type_pct_of_group,
    ROUND(SUM(price)*100/ SUM(SUM(price)) OVER (PARTITION BY sales_channel_id),2) AS type_pct_of_channel,
    ROUND(SUM(price)*100/ SUM(SUM(price)) OVER (),2) AS type_sale_total_perc

FROM transactions_train t
JOIN articles a USING(article_id)
GROUP BY sales_channel_id,product_group_name,product_type_name
ORDER BY sales_channel_id,group_sale DESC,type_sale DESC;

-- 5. Product concentration: rank sold products by sales, split into ten groups, and calculate cumulative shares.
WITH product_sales AS(
	SELECT 
		article_id,
        SUM(price) AS sales,
        COUNT(*) AS units
	FROM transactions_train
    GROUP BY article_id),
    ranked AS(
    SELECT *,
		NTILE(10) OVER (ORDER BY sales DESC, article_id) AS decile
	FROM product_sales)
    
SELECT 
	decile,
    COUNT(*) AS product_cnt,
    SUM(sales) AS sales,
    ROUND(SUM(sales)*100/SUM(SUM(sales)) OVER(),2) AS sale_pec,
    ROUND(SUM(SUM(sales)) OVER (ORDER BY decile)*100/SUM(SUM(sales)) OVER(),2) AS cum_sales_pct
FROM ranked r
GROUP BY decile
ORDER BY decile;

-- 6. Top-product mix: identify categories contributing to the top approximately 10% of sold products.
WITH product_sales AS(
	SELECT 
		article_id,
        SUM(price) AS sales,
        COUNT(*) AS units
	FROM transactions_train
    GROUP BY article_id),
    ranked AS(
    SELECT *,
		NTILE(10) OVER (ORDER BY sales DESC, article_id) AS decile
	FROM product_sales)
    
SELECT 
	product_group_name,
    COUNT(*) AS top_product_cnt,
    SUM(sales) AS top_sales,
    ROUND(SUM(sales)*100/SUM(SUM(sales)) OVER (),2) AS pct_of_top10_sales
FROM ranked
LEFT JOIN articles USING(article_id)
WHERE decile=1
GROUP BY product_group_name
ORDER BY top_sales DESC;

-- 7. Monthly product-type performance: sales, units, sold products, units per product, and average price.
WITH monthly AS(
	SELECT 
    DATE_FORMAT(t_dat,'%Y-%m')AS month,
    SUM(price) AS sales,
    COUNT(*) AS unit_sold,
    COUNT(DISTINCT article_id) AS articles_sold,
    COUNT(*) / COUNT(DISTINCT article_id) AS units_per_article,
    SUM(price)/COUNT(*) AS avg_price,
    product_type_name
    FROM transactions_train
    JOIN articles USING(article_id)
    GROUP BY month,product_type_name)
    
SELECT 
	month,
    product_type_name,
    sales,
    unit_sold,
    ROUND((sales-LAG(sales) OVER w)*100/LAG(sales) OVER w,2) AS sales_growth_rate,
    articles_sold,
    ROUND((articles_sold-LAG(articles_sold) OVER w)*100/LAG(articles_sold) OVER w,2) AS articles_sold_growth_rate,
    units_per_article,
    ROUND((units_per_article-LAG(units_per_article) OVER w)*100/LAG(units_per_article) OVER w,2) AS units_per_article_growth_rate,
    avg_price,
    ROUND((avg_price-LAG(avg_price) OVER w)*100/LAG(avg_price) OVER w,2) AS avg_price_growth_rate 
FROM monthly
WINDOW w AS (PARTITION BY product_type_name ORDER BY month)
ORDER BY product_type_name, month;