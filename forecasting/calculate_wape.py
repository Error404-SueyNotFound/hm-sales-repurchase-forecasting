"""Compute WAPE from daily forecast records; run the whole file in Spyder.

Input: results/run_01/daily_predictions.csv.
Outputs in the same directory: wape_test.csv, wape_validation_folds.csv,
and wape_validation_summary.csv. Rerunning updates these three files.
A WAPE_pct value of 10.26 means 10.26 percent, not 0.1026."""
from pathlib import Path

import numpy as np
import pandas as pd


# 1. Resolve the input relative to this script, independently of the Spyder working directory.
result_dir = Path(__file__).resolve().parent / "results" / "run_01"
df = pd.read_csv(result_dir / "daily_predictions.csv", parse_dates=["date"])

# 2. Reject missing or duplicate observations that could distort error totals.
required = ["phase", "fold", "model", "date", "actual", "predicted"]
if df.empty or df[required].isna().any().any():
    raise ValueError("预测明细为空或包含缺失值，请检查输入文件。")
if df.duplicated(["phase", "fold", "model", "date"]).any():
    raise ValueError("同一阶段、轮次、模型、日期出现重复记录。")
if not np.isfinite(df[["actual", "predicted"]].to_numpy()).all():
    raise ValueError("真实值或预测值含有无穷大等无效数值。")
if (df["actual"] < 0).any():
    raise ValueError("本销量分析要求真实销量非负。")

# Models must use identical dates and actuals within each fold for a fair comparison.
models = set(df["model"])
for (phase, fold), block in df.groupby(["phase", "fold"]):
    counts = block.groupby("date")["model"].nunique()
    actual_counts = block.groupby("date")["actual"].nunique()
    if not counts.eq(len(models)).all() or not actual_counts.eq(1).all():
        raise ValueError(f"{phase} 第 {fold} 轮：模型日期覆盖或真实销量不一致。")

# 3. Calculate daily absolute errors, then aggregate by phase, fold, and model.
# Do not subtract aggregate forecasts from aggregate actuals: signed errors can cancel.
df["absolute_error"] = (df["predicted"] - df["actual"]).abs()
wape = df.groupby(["phase", "fold", "model"], as_index=False).agg(
    forecast_start=("date", "min"),
    forecast_end=("date", "max"),
    days=("date", "nunique"),
    actual_units=("actual", "sum"),
    absolute_error_units=("absolute_error", "sum"),
)

# 4. WAPE = sum of absolute errors / sum of actual units * 100.
# When actual total units are zero, WAPE is undefined; preserve a missing value.
wape["WAPE_pct"] = (
    wape["absolute_error_units"]
    / wape["actual_units"].replace(0, np.nan)
    * 100
)

# 5. Sort holdout results by WAPE and retain separate validation-fold results.
test = wape[wape["phase"].eq("test")].sort_values(["fold", "WAPE_pct"])
validation = wape[wape["phase"].eq("validation")].sort_values(
    ["fold", "WAPE_pct"]
)

# Validation summary: the arithmetic mean of fold WAPEs, consistent with mean_WAPE_pct.
# This is not WAPE recalculated after pooling all validation dates.
validation_summary = validation.groupby("model", as_index=False).agg(
    completed_folds=("fold", "nunique"),
    valid_WAPE_folds=("WAPE_pct", "count"),
    mean_WAPE_pct=("WAPE_pct", "mean"),
    sd_WAPE_pct=("WAPE_pct", "std"),
).sort_values("mean_WAPE_pct")

# 6. Preserve calculation precision in CSV files; display two decimal places.
outputs = {
    "wape_test.csv": test,
    "wape_validation_folds.csv": validation,
    "wape_validation_summary.csv": validation_summary,
}
for filename, table in outputs.items():
    table.to_csv(result_dir / filename, index=False, encoding="utf-8-sig")

print("测试集：各模型 WAPE（%），越低越好")
print(test[["model", "days", "WAPE_pct"]].round(2).to_string(index=False))
print("\n验证集：各模型每轮 WAPE 的平均值（%）")
print(validation_summary.round(2).to_string(index=False))
print("\n结果已保存至：", result_dir)
