# H&M 日销量预测与分析

输入为SQL导出的 `daily_sales.csv`：date是日期，units是每日购买件数。该数据不是订单数，也不是整个H&M市场的总销量。

## 在Spyder中使用

1. 使用已安装numpy、pandas、statsmodels、matplotlib的Python环境。
2. 打开本文件夹的 `run_forecasting.py`，运行整份文件。
3. 程序依次进行5轮验证、1轮测试，再保存明细、误差分析、4张图和中文报告。
4. 每次新建 `results/run_XX`；不会覆盖以前的实验。控制台信息同时保存在 `run_log.txt`。
5. 只想更新分析而不训练模型时，运行 `analyze_forecasts.py`，它读取最新完整回测。

不要只把代码留在untitled标签里。上述三个.py文件已经保存，可以随时重新打开。

终端运行：

```bash
cd '/Users/hamina/Desktop/SQL/H&M/forecasting'
.venv/bin/python run_forecasting.py
```

## 文件职责

- `backtest.py`：输入校验、6种模型、历史切分、验证选模和测试评分。
- `analyze_forecasts.py`：逐日误差核验、WAPE、验证稳定性、绘图和中文报告。
- `run_forecasting.py`：完整运行入口并保存日志。
- `calculate_wape.py`：此前保留的独立教学代码，仍固定读取run_01。新运行的WAPE由analyze_forecasts.py保存到对应新目录。
- `requirements.txt`：本次环境版本。已有环境可直接运行，无需重复安装。

## 固定实验

模型：SeasonalNaive7、WeekdayMean4、ARMA(1,1)、ARIMA(1,1,1)、SARIMA(1,1,1)(0,1,1,7)、7天加性季节/阻尼趋势Holt-Winters。

每轮训练窗口向后扩展，一次预测28天，不在预测窗口中更新。验证5轮，按平均MAE选模；最后28天测试。所有模型同样使用非负预测限制。未引入外部市场、价格、库存、促销或黑五标签，没有利用测试排名调整参数。

本次重跑属于原实验的复现。测试结果之前已经查看，不应宣称是新的独立盲测。

## 输出用途

| 文件 | 内容 |
|---|---|
| input_daily_sales.csv | 本次输入的日销量快照 |
| selection.json | 验证选中的模型、期限、环境版本、输入SHA-256 |
| daily_predictions.csv | 每个阶段、轮次、模型、日期的真实和预测销量 |
| backtest_scores.csv | 每轮MAE、MSE、RMSE、WAPE、MASE7、bias |
| validation_model_comparison.csv | 5轮验证平均指标与选模资格 |
| final_test_comparison.csv | 最后28天各模型表现，标记预先选中模型 |
| model_issues.csv | 运行警告和模型错误；空表代表本次未捕获问题 |
| daily_prediction_errors.csv | 全部逐日明细，加有符号误差、绝对误差、平方误差 |
| test_model_totals.csv | 实际总销量、预测总销量及重算指标 |
| wape_test.csv | 测试集WAPE及其分子、分母 |
| wape_validation_folds.csv | 每轮验证WAPE及其分子、分母 |
| wape_validation_summary.csv | 各模型验证WAPE的简单平均和标准差 |
| validation_fold_comparison.csv | 每轮相对同轮基准的MAE改善比例 |
| validation_stability.csv | 验证汇总、击败基准的轮数、最好和最差轮MAE |
| test_actual_vs_forecast.csv | 一行一天，实际值及6个模型预测，便于直接比较 |
| test_weekday_errors.csv | 测试期按星期几分组的误差；每组只有4天 |
| test_largest_errors.csv | 每个模型绝对误差最大的3天 |
| comparison_with_run_01.csv | 与第一次运行的指标差异（旧结果存在时） |
| analysis_checks.json | 本次核验记录 |
| python_analysis_findings.md | 中文分析报告，每次运行独立保留 |
| run_log.txt | 运行进度、最终表格和错误堆栈 |

4张PNG分别展示：真实销量与6模型预测、测试误差、验证期相对基准表现、完整历史与评估区间。报告目录另保存一份最新中文报告，链接对应本次图片。

## 重要口径

WAPE和bias的百分比列中10代表10%。MASE7分母来自训练期，不等于与当前测试基准比较。验证平均WAPE是5轮简单平均，不是全部日期合并后的比率。平均误差、方差和百分比指标没有通用的行业合格线。

测试排名不替代验证选模。不能把单一窗口最好的模型宣布为长期最优模型，也不能把销量预测直接解释为利润或库存优化。
