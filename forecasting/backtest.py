"""Historical H&M daily-unit backtesting. Run run_forecasting.py for the full workflow.

Compare six fixed specifications over five validation folds and a 28-day holdout.
Select using mean validation MAE; never update forecasts with holdout observations.
Each run creates a new output directory and preserves earlier results."""
import hashlib
import json
import platform
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels

ROOT = Path(__file__).resolve().parent
MODELS = ["SeasonalNaive7", "WeekdayMean4", "ARMA11", "ARIMA111",
          "SARIMA111_011_7", "HoltWinters7"]
HORIZON = 28
FOLDS = 5


def next_output_dir():
    """Create a numbered output directory without overwriting previous experiments."""
    parent = ROOT / "results"
    parent.mkdir(exist_ok=True)
    for number in range(1, 10000):
        directory = parent / f"run_{number:02d}"
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            continue
    raise RuntimeError("结果目录编号已用完。")


def load_daily(path):
    """Validate daily units; reject missing dates rather than replacing unknown observations with zero."""
    df = pd.read_csv(path, usecols=["date", "units"])
    df["date"] = pd.to_datetime(df["date"], errors="raise")
    if df["date"].isna().any() or df["date"].duplicated().any():
        raise ValueError("日期缺失或重复。")
    df["units"] = pd.to_numeric(df["units"], errors="raise")
    y = df.set_index("date")["units"].sort_index().astype(float)
    if not np.isfinite(y.to_numpy()).all() or (y < 0).any():
        raise ValueError("销量必须为有限、非负的数值。")
    if not np.equal(y, np.floor(y)).all():
        raise ValueError("本项目预测购买件数，应为整数。")
    if not y.index.equals(pd.date_range(y.index.min(), y.index.max(), freq="D")):
        raise ValueError("每日数据有缺口，请先查明原因。")
    if len(y) < 365 + (FOLDS + 1) * HORIZON or y.max() == 0:
        raise ValueError("数据不足，或全部销量为0。")
    return y.asfreq("D")


def forecast(name, train, horizon):
    """Each model receives only observations available before its forecast origin."""
    if name == "SeasonalNaive7":
        # Baseline: repeat the final seven training observations for the next four weeks.
        pred = np.resize(train.iloc[-7:].to_numpy(), horizon)
    elif name == "WeekdayMean4":
        # Average each weekday over the final four training weeks; this is not the MA term in ARMA.
        last28 = train.iloc[-28:]
        means = last28.groupby(last28.index.day_of_week).mean()
        dates = pd.date_range(train.index[-1] + pd.Timedelta(days=1), periods=horizon)
        pred = np.array([means.loc[d.day_of_week] for d in dates])
    else:
        # Scale only by the training mean for optimization, then restore forecasts to units.
        scale = max(float(train.mean()), 1.0)
        z = train / scale
        if name == "HoltWinters7":
            from statsmodels.tsa.holtwinters import ExponentialSmoothing
            fit = ExponentialSmoothing(
                z, trend="add", damped_trend=True, seasonal="add",
                seasonal_periods=7, initialization_method="estimated",
            ).fit(optimized=True)
            optimizer = getattr(fit, "mle_retvals", None)
            if optimizer is not None and not optimizer.get("success", True):
                raise RuntimeError("Holt-Winters优化未收敛。")
        else:
            from statsmodels.tsa.statespace.sarimax import SARIMAX
            specs = {
                "ARMA11": ((1, 0, 1), (0, 0, 0, 0), "c"),
                "ARIMA111": ((1, 1, 1), (0, 0, 0, 0), "n"),
                "SARIMA111_011_7": ((1, 1, 1), (0, 1, 1, 7), "n"),
            }
            order, seasonal_order, trend = specs[name]
            fit = SARIMAX(
                z, order=order, seasonal_order=seasonal_order, trend=trend,
                enforce_stationarity=True, enforce_invertibility=True,
            ).fit(disp=False, maxiter=300)
            if not fit.mle_retvals.get("converged", False):
                raise RuntimeError("ARIMA系列优化未收敛。")
        pred = np.asarray(fit.forecast(horizon), dtype=float) * scale
    if not np.isfinite(pred).all():
        raise ValueError("预测包含无效数值。")
    # Apply the same nonnegative clipping rule to every model; retain decimals for scoring.
    return np.maximum(pred, 0)


def metrics(actual, pred, train):
    """Compare forecasts with actual units; positive bias indicates overprediction."""
    error = np.asarray(pred) - np.asarray(actual)
    train_values = np.asarray(train)
    seasonal_scale = np.mean(np.abs(train_values[7:] - train_values[:-7]))
    total = float(np.sum(actual))
    mae = float(np.mean(np.abs(error)))
    return {
        "MAE": mae,
        "MSE": float(np.mean(error ** 2)),
        "RMSE": float(np.sqrt(np.mean(error ** 2))),
        "WAPE_pct": float(np.sum(np.abs(error)) / total * 100) if total else np.nan,
        "MASE7": mae / seasonal_scale if seasonal_scale else np.nan,
        "bias_pct": float(np.sum(error) / total * 100) if total else np.nan,
    }


def evaluate(y, start, phase, fold, scores, predictions, issues):
    """Use an expanding training window and a fixed 28-day forecast horizon."""
    train = y.iloc[:start]
    actual = y.iloc[start:start + HORIZON]
    assert len(actual) == HORIZON and train.index.max() < actual.index.min()
    for model in MODELS:
        caught = []
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                pred = forecast(model, train, HORIZON)
            scores.append({
                "phase": phase, "fold": fold, "model": model,
                "train_end": train.index[-1].date().isoformat(),
                "forecast_start": actual.index[0].date().isoformat(),
                "forecast_end": actual.index[-1].date().isoformat(),
                **metrics(actual.to_numpy(), pred, train),
            })
            for date, observed, predicted in zip(actual.index, actual.to_numpy(), pred):
                predictions.append({"phase": phase, "fold": fold, "model": model,
                                    "date": date.date().isoformat(),
                                    "actual": observed, "predicted": predicted})
            print(f"{phase} fold={fold} {model}: completed", flush=True)
        except Exception as exc:
            issues.append({"phase": phase, "fold": fold, "model": model,
                           "level": "error", "message": str(exc)})
            print(f"{phase} fold={fold} {model}: FAILED: {exc}", flush=True)
        finally:
            for warning in caught:
                issues.append({"phase": phase, "fold": fold, "model": model,
                               "level": "warning", "message": str(warning.message)})


def run_backtest(output_dir=None):
    """Save the validation-based selection before testing; do not reselect on holdout performance."""
    output_dir = next_output_dir() if output_dir is None else Path(output_dir)
    input_path = ROOT / "daily_sales.csv"
    y = load_daily(input_path)
    print(f"输入：{len(y)}天，{int(y.sum()):,}件。输出：{output_dir}", flush=True)
    y.rename("units").rename_axis("date").to_csv(output_dir / "input_daily_sales.csv")
    test_start = len(y) - HORIZON
    scores, predictions, issues = [], [], []
    for fold in range(1, FOLDS + 1):
        start = test_start - (FOLDS - fold + 1) * HORIZON
        evaluate(y, start, "validation", fold, scores, predictions, issues)

    val = pd.DataFrame(scores)
    if val.empty:
        raise RuntimeError("所有验证模型均失败。")
    summary = val.groupby("model").agg(
        completed_folds=("fold", "nunique"), mean_MAE=("MAE", "mean"),
        sd_MAE=("MAE", "std"), mean_RMSE=("RMSE", "mean"),
        mean_WAPE_pct=("WAPE_pct", "mean"), mean_MASE7=("MASE7", "mean"),
    ).reindex(MODELS).rename_axis("model").reset_index()
    summary["completed_folds"] = summary["completed_folds"].fillna(0).astype(int)
    summary["eligible_for_selection"] = summary["completed_folds"].eq(FOLDS)
    summary = summary.sort_values(["mean_MAE", "model"])
    summary.to_csv(output_dir / "validation_model_comparison.csv", index=False)
    eligible = summary[summary["eligible_for_selection"]]
    if eligible.empty:
        raise RuntimeError("没有模型完成全部5轮验证，不能选模。")
    selected = eligible.iloc[0]["model"]
    selection = {
        "selected_model": selected, "selection_metric": "mean validation MAE",
        "horizon": HORIZON, "validation_folds": FOLDS,
        "input_start": str(y.index[0].date()),
        "final_train_end": str(y.index[test_start - 1].date()),
        "test_start": str(y.index[test_start].date()), "test_end": str(y.index[-1].date()),
        "python_version": platform.python_version(), "pandas_version": pd.__version__,
        "numpy_version": np.__version__, "statsmodels_version": statsmodels.__version__,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "note": "Fixed initial model orders; reproduction of an already viewed holdout, not a new blind test.",
    }
    (output_dir / "selection.json").write_text(
        json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"验证集选中：{selected}。开始固定测试期评估。", flush=True)
    evaluate(y, test_start, "test", 1, scores, predictions, issues)

    scores_df = pd.DataFrame(scores)
    scores_df.to_csv(output_dir / "backtest_scores.csv", index=False)
    pd.DataFrame(predictions).to_csv(output_dir / "daily_predictions.csv", index=False)
    pd.DataFrame(issues, columns=["phase", "fold", "model", "level", "message"]).to_csv(
        output_dir / "model_issues.csv", index=False)
    test = scores_df[scores_df["phase"].eq("test")].copy()
    test["selected_on_validation"] = test["model"].eq(selected)
    base = test.loc[test["model"].eq("SeasonalNaive7"), "MAE"]
    test["MAE_improvement_vs_baseline_pct"] = (
        (1 - test["MAE"] / base.iloc[0]) * 100
        if len(base) and base.iloc[0] > 0 else np.nan)
    test.sort_values("MAE").to_csv(output_dir / "final_test_comparison.csv", index=False)
    if len(scores_df) != len(MODELS) * (FOLDS + 1):
        raise RuntimeError("有模型未成功完成；已有结果保留，请检查model_issues.csv。")
    if selected not in set(test["model"]):
        raise RuntimeError("验证集选中的模型测试失败，不可静默改选其他模型。")
    return output_dir


if __name__ == "__main__":
    run_backtest()
