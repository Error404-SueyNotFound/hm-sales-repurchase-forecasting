"""Analyze saved daily forecasts and export checks, tables, charts, and a Chinese report.

Running this file in Spyder analyzes the latest complete run without refitting models.
Chart labels are English; the narrative report is Chinese."""
import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

# Render directly to files without opening or controlling the Spyder interface.
os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="hm-matplotlib-"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent


def markdown_table(df, columns=None):
    """Create a Markdown table without requiring the optional tabulate dependency."""
    df = df if columns is None else df[columns]
    def display(value):
        if pd.isna(value):
            return "—"
        if isinstance(value, (float, np.floating)):
            return f"{value:,.2f}"
        return str(value)
    lines = ["| " + " | ".join(df.columns) + " |",
             "| " + " | ".join(["---"] * len(df.columns)) + " |"]
    lines += ["| " + " | ".join(display(x) for x in row) + " |"
              for row in df.itertuples(index=False, name=None)]
    return "\n".join(lines)


def latest_complete_run():
    runs = [p for p in (ROOT / "results").glob("run_*")
            if (p / "final_test_comparison.csv").exists()]
    if not runs:
        raise FileNotFoundError("请先运行run_forecasting.py生成回测结果。")
    return max(runs, key=lambda p: int(p.name.split("_")[-1]))


def analyze(output_dir=None):
    out = latest_complete_run() if output_dir is None else Path(output_dir)
    daily = pd.read_csv(out / "daily_predictions.csv", parse_dates=["date"])
    scores = pd.read_csv(out / "backtest_scores.csv")
    validation = pd.read_csv(out / "validation_model_comparison.csv")
    final = pd.read_csv(out / "final_test_comparison.csv")
    selection = json.loads((out / "selection.json").read_text())
    selected = selection["selected_model"]
    snapshot = out / "input_daily_sales.csv"
    source = pd.read_csv(snapshot if snapshot.exists() else ROOT / "daily_sales.csv",
                         parse_dates=["date"]).set_index("date")["units"]

    # 1. Validate actuals, date coverage, and uniqueness before comparing models.
    keys = ["phase", "fold", "model"]
    if daily.duplicated(keys + ["date"]).any() or daily.isna().any().any():
        raise ValueError("每日明细存在重复或缺失。")
    if not np.isfinite(daily[["actual", "predicted"]]).all().all():
        raise ValueError("每日明细包含非有限数值。")
    counts = daily.groupby(keys).size()
    if len(counts) != 36 or not counts.eq(28).all():
        raise ValueError("本项目应有6模型×6轮，每轮28天。")
    np.testing.assert_allclose(daily["actual"], source.reindex(daily["date"]).to_numpy())
    for _, block in daily.groupby(["phase", "fold"]):
        if not block.groupby("date")["model"].nunique().eq(6).all():
            raise ValueError("模型没有使用同一组预测日期。")
    daily["error"] = daily["predicted"] - daily["actual"]
    daily["absolute_error"] = daily["error"].abs()
    daily["squared_error"] = daily["error"] ** 2

    # 2. Recompute metrics from daily forecasts instead of copying precomputed scores.
    grouped = daily.groupby(keys, as_index=False).agg(
        forecast_start=("date", "min"), forecast_end=("date", "max"),
        days=("date", "nunique"), actual_units=("actual", "sum"),
        predicted_units=("predicted", "sum"),
        absolute_error_units=("absolute_error", "sum"),
        MAE=("absolute_error", "mean"), MSE=("squared_error", "mean"),
        mean_error=("error", "mean"),
    )
    grouped["RMSE"] = np.sqrt(grouped["MSE"])
    denominator = grouped["actual_units"].replace(0, np.nan)
    grouped["WAPE_pct"] = grouped["absolute_error_units"] / denominator * 100
    grouped["bias_pct"] = (
        (grouped["predicted_units"] - grouped["actual_units"]) / denominator * 100)
    check = grouped.merge(scores, on=keys, suffixes=("_recomputed", "_original"),
                          validate="one_to_one")
    for metric in ["MAE", "RMSE", "WAPE_pct", "bias_pct"]:
        np.testing.assert_allclose(check[metric + "_recomputed"],
                                   check[metric + "_original"], rtol=1e-10, atol=1e-8)
    daily.to_csv(out / "daily_prediction_errors.csv", index=False, encoding="utf-8-sig")
    test_totals = grouped[grouped["phase"].eq("test")].sort_values("WAPE_pct")
    test_totals.to_csv(out / "test_model_totals.csv", index=False, encoding="utf-8-sig")
    wape_columns = keys + ["forecast_start", "forecast_end", "days",
                           "actual_units", "absolute_error_units", "WAPE_pct"]
    test_totals[wape_columns].to_csv(out / "wape_test.csv", index=False, encoding="utf-8-sig")
    val_rows = grouped[grouped["phase"].eq("validation")]
    val_rows[wape_columns].sort_values(["fold", "WAPE_pct"]).to_csv(
        out / "wape_validation_folds.csv", index=False, encoding="utf-8-sig")
    val_wape = val_rows.groupby("model", as_index=False).agg(
        completed_folds=("fold", "nunique"), mean_WAPE_pct=("WAPE_pct", "mean"),
        sd_WAPE_pct=("WAPE_pct", "std"),
    ).sort_values("mean_WAPE_pct")
    val_wape.to_csv(out / "wape_validation_summary.csv", index=False, encoding="utf-8-sig")

    # 3. Compare each validation fold with its own seasonal-naive baseline.
    val_scores = scores[scores["phase"].eq("validation")].copy()
    baseline = val_scores[val_scores["model"].eq("SeasonalNaive7")][["fold", "MAE"]]
    baseline = baseline.rename(columns={"MAE": "baseline_MAE"})
    fold_comparison = val_scores.merge(baseline, on="fold", validate="many_to_one")
    fold_comparison["MAE_improvement_vs_baseline_pct"] = (
        1 - fold_comparison["MAE"] / fold_comparison["baseline_MAE"].replace(0, np.nan)) * 100
    fold_comparison["beats_baseline"] = fold_comparison["MAE"] < fold_comparison["baseline_MAE"]
    fold_comparison.to_csv(out / "validation_fold_comparison.csv", index=False, encoding="utf-8-sig")
    wins = fold_comparison.groupby("model", as_index=False).agg(
        folds_beating_baseline=("beats_baseline", "sum"),
        worst_fold_MAE=("MAE", "max"), best_fold_MAE=("MAE", "min"),
    )
    stability = validation.merge(wins, on="model", validate="one_to_one")
    stability.to_csv(out / "validation_stability.csv", index=False, encoding="utf-8-sig")

    # 4. Save actual-versus-forecast comparisons, weekday errors, and the largest daily errors.
    test_daily = daily[daily["phase"].eq("test")].copy()
    actual = test_daily.groupby("date")["actual"].first()
    wide = test_daily.pivot(index="date", columns="model", values="predicted")
    wide.insert(0, "actual", actual)
    wide.to_csv(out / "test_actual_vs_forecast.csv", encoding="utf-8-sig")
    test_daily["weekday"] = test_daily["date"].dt.day_of_week
    weekday = test_daily.groupby(["model", "weekday"], as_index=False).agg(
        days=("date", "nunique"), actual_units=("actual", "sum"),
        absolute_error_units=("absolute_error", "sum"), MAE=("absolute_error", "mean"),
        mean_error=("error", "mean"),
    )
    weekday["WAPE_pct"] = weekday["absolute_error_units"] / weekday["actual_units"].replace(0, np.nan) * 100
    weekday.to_csv(out / "test_weekday_errors.csv", index=False, encoding="utf-8-sig")
    worst = test_daily.sort_values("absolute_error", ascending=False).groupby("model").head(3)
    worst.sort_values(["model", "absolute_error"], ascending=[True, False]).to_csv(
        out / "test_largest_errors.csv", index=False, encoding="utf-8-sig")

    # 5. Plot forecasts, holdout errors, validation stability, and evaluation periods.
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 140})
    order = final.sort_values("MAE")["model"].tolist()
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), sharex=True, sharey=True)
    for axis, model in zip(axes.flat, order):
        axis.plot(actual.index, actual.values, color="#202936", label="Actual", linewidth=1.8)
        axis.plot(wide.index, wide[model], color="#2176ae", label="Forecast", linewidth=1.6)
        suffix = " (validation-selected)" if model == selected else ""
        axis.set_title(model + suffix, fontsize=10)
        axis.grid(alpha=0.2)
        axis.xaxis.set_major_locator(mdates.DayLocator(interval=7))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        axis.set_ylabel("Daily units")
    axes.flat[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("28-day holdout: actual sales vs forecasts", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, .96])
    fig.savefig(out / "test_actual_vs_forecast.png")
    plt.close(fig)

    ranked = final.sort_values("WAPE_pct")
    colors = ["#d47529" if m == selected else "#2176ae" for m in ranked["model"]]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for axis, metric, label in zip(axes, ["WAPE_pct", "MAE"], ["WAPE (%)", "MAE (units/day)"]):
        bars = axis.barh(ranked["model"], ranked[metric], color=colors)
        axis.invert_yaxis()
        axis.set_xlabel(label)
        axis.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
        axis.set_xlim(0, ranked[metric].max() * 1.24)
        axis.grid(axis="x", alpha=.2)
    fig.suptitle("Holdout errors | orange = selected using validation")
    fig.tight_layout()
    fig.savefig(out / "test_model_errors.png")
    plt.close(fig)

    matrix = fold_comparison.pivot(index="model", columns="fold", values="MAE_improvement_vs_baseline_pct")
    matrix = matrix.reindex(validation["model"])
    fig, axis = plt.subplots(figsize=(10, 5))
    limit = max(abs(matrix.min().min()), abs(matrix.max().max()), 1)
    heat = axis.imshow(matrix, cmap="RdYlGn", vmin=-limit, vmax=limit, aspect="auto")
    axis.set_xticks(range(5), [f"Fold {i}" for i in matrix.columns])
    axis.set_yticks(range(len(matrix)), matrix.index)
    for i in range(len(matrix)):
        for j in range(5):
            axis.text(j, i, f"{matrix.iloc[i, j]:+.1f}%", ha="center", va="center", fontsize=9)
    axis.set_title("Validation MAE improvement vs same-fold SeasonalNaive7\nPositive = better; negative = worse")
    fig.colorbar(heat, ax=axis, label="MAE improvement (%)")
    fig.tight_layout()
    fig.savefig(out / "validation_baseline_comparison.png")
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(12, 4))
    axis.plot(source.index, source, linewidth=.7, color="#45556c")
    first_val = pd.to_datetime(val_scores["forecast_start"].min())
    test_start = pd.to_datetime(selection["test_start"])
    test_end = pd.to_datetime(selection["test_end"])
    axis.axvspan(first_val, test_start, color="#f4c05c", alpha=.35, label="5 validation windows")
    axis.axvspan(test_start, test_end, color="#61b7a6", alpha=.4, label="28-day holdout")
    axis.set(title="Daily sales and historical evaluation periods", ylabel="Daily units")
    axis.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out / "history_and_evaluation_windows.png")
    plt.close(fig)

    # 6. Compare with the original run without overwriting it or treating forecasts as actuals.
    old_path = ROOT / "results" / "run_01" / "backtest_scores.csv"
    reproduction_note = "没有可用的旧运行用于核对。"
    if old_path.exists() and out.name != "run_01":
        old = pd.read_csv(old_path)
        comparison = scores.merge(old, on=keys, suffixes=("_new", "_old"), validate="one_to_one")
        for metric in ["MAE", "RMSE", "WAPE_pct", "MASE7", "bias_pct"]:
            comparison[metric + "_difference"] = comparison[metric + "_new"] - comparison[metric + "_old"]
        comparison.to_csv(out / "comparison_with_run_01.csv", index=False, encoding="utf-8-sig")
        max_difference = comparison["MAE_difference"].abs().max()
        reproduction_note = f"与run_01匹配{len(comparison)}组模型/轮次结果，MAE最大绝对差为{max_difference:.10f}件。"

    # 7. Generate findings from the current results so reported numbers stay consistent.
    best = final.sort_values("MAE").iloc[0]
    chosen = final.set_index("model").loc[selected]
    base = final.set_index("model").loc["SeasonalNaive7"]
    chosen_stability = stability.set_index("model").loc[selected]
    selected_errors = test_daily[test_daily["model"].eq(selected)]
    largest = selected_errors.loc[selected_errors["absolute_error"].idxmax()]
    rmse_best = final.loc[final["RMSE"].idxmin()]
    arma_tail = wide["ARMA11"].iloc[-7:]
    arima_tail = wide["ARIMA111"].iloc[-7:]
    weakest_weekday = weekday[weekday["model"].eq("WeekdayMean4")].sort_values("WAPE_pct").iloc[-1]
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    dates = val_scores[["fold", "train_end", "forecast_start", "forecast_end"]].drop_duplicates().sort_values("fold")
    issues = pd.read_csv(out / "model_issues.csv")
    status = {"prediction_rows": len(daily), "model_fold_results": len(scores),
              "input_days": len(source), "input_units": int(source.sum()),
              "actuals_match_input": True, "recomputed_metrics_match": True,
              "issues": len(issues), "reproduction": reproduction_note}
    (out / "analysis_checks.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# H&M Python 日销量预测：回测分析

本报告使用 `{out.name}` 的重新运行结果。仅预测数据集内每日购买件数，不代表H&M全部市场销量，也不是2026年预测。价格、库存、促销和国家信息未作为模型输入。

## 1. 任务与实验设计

- 输入：{len(source)}天，{int(source.sum()):,}件，{source.index.min().date()}至{source.index.max().date()}。
- 每次在预测起点一次性预测之后28天，不用预测区间的真实值更新模型。
- 5个连续、不重叠的验证窗口；每轮训练集向后扩展。
- 根据验证集平均MAE选模型，选定后才在程序中计算测试指标。
- 最终训练截止{selection['final_train_end']}；固定测试期{selection['test_start']}至{selection['test_end']}。
- 本次是对已看过测试结果的同一实验进行复现，不是新的独立盲测。没有因测试排名而更改阶数或重新选模型。

{markdown_table(dates)}

## 2. 六个模型分别做什么

| 模型 | 本次设置与含义 |
|---|---|
| SeasonalNaive7 | 重复训练末尾7天销量；简单周周期基准 |
| WeekdayMean4 | 最近4周同一星期几的平均销量 |
| ARMA11 | ARMA(1,1)，以一期销量和一期误差描述相关性；含常数；没有显式季节项 |
| ARIMA111 | ARIMA(1,1,1)，先对销量作一阶差分，再描述差分的相关性；无趋势常数 |
| SARIMA111_011_7 | SARIMA(1,1,1)(0,1,1,7)，在普通差分外加入7天季节差分与季节误差项 |
| HoltWinters7 | 加性水平、阻尼趋势和7天加性季节项的指数平滑 |

ARMA中的MA是过去误差项的加权关系，不是WeekdayMean4的销量平均。所有模型使用同一训练范围，统一把负预测截为0，保留小数计算误差。这里比较的是六个固定设置，不代表整个模型家族的最优性能。

## 3. 先看验证集：为何选中{selected}

{markdown_table(stability, ['model','completed_folds','mean_MAE','sd_MAE','mean_WAPE_pct','folds_beating_baseline'])}

`mean_MAE`为5轮MAE的简单平均，是选模依据。`mean_WAPE_pct`为5轮WAPE的简单平均，不是将全部验证日期合并后计算的WAPE。`sd_MAE`表示轮次之间的误差波动，轮次难度、销量规模不同也会影响它。

{selected}的验证平均MAE为{chosen_stability['mean_MAE']:,.2f}件，在5轮中有{int(chosen_stability['folds_beating_baseline'])}轮优于同轮季节性朴素基准。平均表现最好不表示每一轮都最好，应结合逐轮比较图查看优势是否集中在个别窗口。

## 4. 最终28天：与真实销量直接比较

测试期实际总销量为{int(actual.sum()):,}件，日均{actual.mean():,.2f}件。

{markdown_table(final, ['model','MAE','RMSE','WAPE_pct','MASE7','bias_pct','selected_on_validation','MAE_improvement_vs_baseline_pct'])}

- 测试期MAE最小的是{best['model']}：MAE {best['MAE']:,.2f}件，WAPE {best['WAPE_pct']:.2f}%，相对基准MAE改善{best['MAE_improvement_vs_baseline_pct']:.2f}%。这是事后测试排名，不能替代验证集选模记录。
- 预先按验证集选中的{selected}：MAE {chosen['MAE']:,.2f}件，WAPE {chosen['WAPE_pct']:.2f}%，相对基准MAE改善{chosen['MAE_improvement_vs_baseline_pct']:.2f}%（负数表示更差）。
- 简单基准SeasonalNaive7：MAE {base['MAE']:,.2f}件，WAPE {base['WAPE_pct']:.2f}%。复杂模型需要与同一测试期的基准比较。
- RMSE最低的是{rmse_best['model']}（{rmse_best['RMSE']:,.2f}件）。MAE和RMSE排名可能不同，因为RMSE更重视较大的日误差。
- 验证与测试排名发生变化，说明本次选模效果没有稳定延续；本实验没有证明具体业务原因，也不能据此认定某模型永远更好。

实际总销量与预测总量对照如下。真实值在模型行中重复，是为了对照，不能跨模型相加：

{markdown_table(test_totals, ['model','actual_units','predicted_units','absolute_error_units','bias_pct'])}

这里还说明“预测总量接近实际”与“每天都预测准确”不同。季节性朴素法的总量bias绝对值为{abs(base['bias_pct']):.2f}%，但日误差的WAPE为{base['WAPE_pct']:.2f}%，不同日期的高估、低估会在总量中抵消。

### 从图上看六个模型

- ARMA11：本次最后7个预测值集中在{arma_tail.min():,.0f}—{arma_tail.max():,.0f}件，接近水平线；没有显式周季节项。在本测试期实际销量较低的日子容易高估，图上可见这种差异，但不能据此推断其他时期也一定如此。
- ARIMA111：最后7个预测值集中在{arima_tail.min():,.0f}—{arima_tail.max():,.0f}件，同样缺少明显周内波动。固定起点的多步预测没有持续接收新真实值，变平不意味着程序停止工作。
- SARIMA和Holt-Winters：预测具有7天起伏，但仍未准确跟随所有日度低点。最低MAE与最低RMSE落在不同模型，评价指标的侧重点有影响；没有进行显著性检验，不能把微小差异描述为确定优势。
- SeasonalNaive7：机械重复最近一周，透明、便于比较，是需要保留的基准，不因简单就自动劣于复杂模型。
- WeekdayMean4：在本测试期{weekday_names[int(weakest_weekday['weekday'])]}的WAPE最高，达到{weakest_weekday['WAPE_pct']:.2f}%。可检查最近4周该星期的水平是否适合测试期；仅4个测试观测，暂不推断长期规律。

## 5. 偏差方向、每日大误差与星期结构

{selected}测试期bias为{chosen['bias_pct']:.2f}%。本代码以“预测−实际”为误差，正值表示总体高估、负值表示总体低估。WAPE先对每日误差取绝对值，不能被不同日期的正负偏差抵消。

该模型28天中有{int((selected_errors['error'] > 0).sum())}天高估、{int((selected_errors['error'] < 0).sum())}天低估。绝对误差最大的日期是{largest['date'].date()}：实际{largest['actual']:,.0f}件，预测{largest['predicted']:,.2f}件，绝对误差{largest['absolute_error']:,.2f}件。

`test_actual_vs_forecast.csv`及同名图片直接列出真实值与预测值。`test_largest_errors.csv`保留每个模型误差最大的3天，可用于查找共同遗漏的销量波动；不能仅凭异常日期给它贴促销标签。

`test_weekday_errors.csv`中weekday=0表示周一，6表示周日。每个星期几在28天内只有4个观测，结果仅作排查线索，不能作为长期星期效应的充分证据。销量还受到库存等未观察因素影响，不等于无约束需求。

## 6. 指标如何解释

| 指标 | 定义和用途 |
|---|---|
| MAE | 每日绝对误差平均值，单位是件；越低越好 |
| MSE | 每日误差平方的平均值，单位件²，数值大不等于模型一定差 |
| RMSE | MSE开平方，单位件，对较大误差更敏感 |
| WAPE_pct | 每日绝对误差之和÷实际总销量×100；10表示10%，不是直接的准确率 |
| MASE7 | 测试MAE÷训练期销量与7天前之差的平均绝对值；小于1不保证击败同一测试期的季节性朴素法 |
| bias_pct | 预测总量减实际总量，再除以实际总量×100；反映方向，可发生正负抵消 |
| MAE_improvement_vs_baseline_pct | (1−模型MAE÷同一测试窗口基准MAE)×100；负值表示劣于基准 |

分母为0时相应比率无定义，保存为空值。不能把WAPE机械转换成“准确率=100%−WAPE”，也不能设一个适用于所有商品、规模和预测期限的统一合格线。

## 7. 可以写进项目报告的结论

1. 在相同数据与28天预测期限下，比较了两种简单基准、ARMA、ARIMA、SARIMA及Holt-Winters六种设置。
2. 采用5轮扩展窗口验证，以平均MAE选择{selected}，并保留固定测试窗口检验其表现。
3. 验证最优模型未稳定保持测试优势，应保留这一结果，而不是事后替换选模记录。
4. 测试期{best['model']}取得最低MAE，但只有一个最终窗口，不能推断长期优势或生产环境效果。
5. 若继续调参，当前测试期已经被查看，后续结果应标为探索性；新的可靠比较需要更多未用于决策的时期或嵌套时间验证。
6. 本分析未引入促销、库存、价格、商品级特征，不把预测错误归因于某个未经核实的活动。没有库存与缺货成本，不能直接估计备货利润。

## 8. 运行核验与复现

- 6模型×6轮×28天，共{len(daily)}条预测；每个模型使用同一轮的相同日期。
- 所有真实值与输入日销量逐日核对一致；MAE、RMSE、WAPE、bias由预测明细独立重算并与回测表核对一致。
- 本次记录的警告/错误共{len(issues)}条，详见model_issues.csv（空表保留列名）。
- {reproduction_note}
- 输入日销量快照、原始CSV的SHA-256和依赖版本已保存，便于追溯。

## 9. 图表

![真实销量与六模型预测](test_actual_vs_forecast.png)

![测试集误差比较](test_model_errors.png)

![逐轮验证与基准比较](validation_baseline_comparison.png)

![历史销量与评估区间](history_and_evaluation_windows.png)
"""
    (out / "python_analysis_findings.md").write_text(report, encoding="utf-8")
    reports = ROOT.parent / "reports"
    reports.mkdir(exist_ok=True)
    # Adjust relative image links in the reports copy; keep each run-specific report.
    linked_report = report
    for name in ["test_actual_vs_forecast", "test_model_errors", "validation_baseline_comparison", "history_and_evaluation_windows"]:
        linked_report = linked_report.replace(f"]({name}.png)", f"](../forecasting/results/{out.name}/{name}.png)")
    (reports / "python_analysis_findings.md").write_text(linked_report, encoding="utf-8")
    print("\n验证集表现：\n" + stability.round(2).to_string(index=False))
    print("\n最终测试表现：\n" + final.round(2).to_string(index=False))
    print("\n" + reproduction_note)
    print("\n分析报告：", reports / "python_analysis_findings.md")
    return out


if __name__ == "__main__":
    analyze()
