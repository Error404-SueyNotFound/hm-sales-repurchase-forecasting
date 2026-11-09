-- Target: daily purchase units across all channels (transaction rows), not orders or unconstrained demand.
-- Export the complete Workbench result to H&M/forecasting/daily_sales.csv.
-- Use Don't Limit and retain the date and units column names.
USE hm_analysis;
SELECT t_dat AS date, COUNT(*) AS units
FROM transactions_train
GROUP BY t_dat
ORDER BY t_dat;
