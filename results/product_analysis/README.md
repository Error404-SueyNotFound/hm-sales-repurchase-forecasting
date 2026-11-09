# 任务三：商品与品类分析结果

SQL：`../../code/03_product_analysis.sql`。每段前已添加中文简短说明，字段名与原分析口径保留。

修改前备份：`../../code/03_product_analysis_original.sql`。经用户同意，仅修正第三段窗口函数的月份别名引用：将 5 处 `PARTITION BY month` 中的 `month` 换为 `DATE_FORMAT(t_dat,'%Y-%m')`。这是 MySQL 兼容性修复，统计口径不变。

七段均通过本地 MySQL Workbench 在 `hm_analysis` 上实际执行；导出时使用 Don’t Limit。CSV 包含表头，下列行数不含表头。

| 段落 | 分析标题 | 文件名 | 数据行数 | 查询耗时（秒，不含导出） |
|---|---|---|---:|---:|
| 1 | 整体品类销售结构 | [category_sales_structure.csv](category_sales_structure.csv) | 131 | 65.738 |
| 2 | 季节品类销售结构（跨年份汇总） | [seasonal_category_sales_structure.csv](seasonal_category_sales_structure.csv) | 496 | 68.865 |
| 3 | 月度品类销售结构 | [monthly_category_sales_structure.csv](monthly_category_sales_structure.csv) | 2,738 | 94.181 |
| 4 | 分渠道品类销售结构 | [channel_category_sales_structure.csv](channel_category_sales_structure.csv) | 247 | 77.055 |
| 5 | 商品销售集中度（销售额十分位） | [product_sales_concentration.csv](product_sales_concentration.csv) | 10 | 7.077 |
| 6 | 销售额前约 10% 商品的品类构成 | [top_decile_product_category_mix.csv](top_decile_product_category_mix.csv) | 11 | 7.239 |
| 7 | 细分类月度销售表现及驱动指标 | [monthly_product_type_performance.csv](monthly_product_type_performance.csv) | 2,713 | 63.253 |

## 核对结果

- 七张 CSV 的行数均与 Workbench 返回行数一致。
- 整体、季节、月度、渠道、商品十分位与细分类月度表的全时期销售额一致（允许浮点累加误差）。
- 细分类月度表购买件数合计为 31,788,324，与完整交易表记录数一致。
- 商品十分位累计占比最终为 100%；第一组的商品数量、销售额与头部商品品类构成表一致。

## 报告使用口径

- price 为标准化价格，不标注人民币、美元等实际货币单位。
- group_sale 在细分类行中重复出现，不能对该列直接跨行求和；需要汇总销售额时使用 type_sale。
- 季节表将不同年份同名季节合并；首尾数据覆盖不完整，不能只凭季节总额推断季节需求强弱。
- 数据范围为 2018-09-20 至 2020-09-22，首尾月份不完整。
- NTILE(10) 基于有成交商品；第一组是排名前约 10% 的商品，不是前 10 件商品。
- 第七段按 product_type_name 汇总，第三段按 product_group_name + product_type_name 汇总，两张表的行数可以不同。
- 第七段检测到 32 处同一细分类相邻结果行跨过了无记录月份；这些行的 LAG 比较的是上一个有记录月份，不能直接解释为连续月份环比。

原第三段首次执行曾报 Error 1054（Unknown column month in window partition by），修正后成功；原始报错版本仅作备份，不作为重跑入口。
