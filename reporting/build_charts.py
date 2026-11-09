"""Generate project charts from exported aggregates without modifying SQL or source data."""
from pathlib import Path
import os
import tempfile
import numpy as np
import pandas as pd
os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="hm-report-font-"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
ENGLISH = os.environ.get("HM_CHART_LANGUAGE", "zh") == "en"
OUT = ROOT / "reports" / ("figures_en" if ENGLISH else "figures")
OUT.mkdir(parents=True, exist_ok=True)
R = ROOT / "results" / "repurchase_analysis"
P = ROOT / "results" / "product_analysis"
font_path = Path("/System/Library/Fonts/STHeiti Light.ttc")
if font_path.exists() and not ENGLISH:
    font_manager.fontManager.addfont(str(font_path))
    plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlepad": 12, "figure.dpi": 160})
BLUE, TEAL, ORANGE = "#23658c", "#24918b", "#ca7438"


TRANSLATIONS = {'月度销售额（标准化金额，千）': 'Monthly sales (normalized, thousands)', '月度购买件数（万件）': 'Monthly units (10,000s)', '不完整月份': 'Incomplete month', '渠道1': 'Channel 1', '渠道2': 'Channel 2', '当月销售额占比（%）': 'Monthly sales share (%)', '渠道1无记录': 'No Channel 1 records', '上身服装': 'Upper-body', '下身服装': 'Lower-body', '全身服装': 'Full-body', '泳装': 'Swimwear', '内衣': 'Underwear', '鞋类': 'Shoes', '配饰': 'Accessories', '睡衣': 'Nightwear', '整体销售额占比（%）': 'Share of total sales (%)', '主要大类销售构成': 'Sales by category', '前10%贡献61.67%': 'Top 10% contribute 61.67%', '销售额排名靠前的商品比例（约%）': 'Top-selling products (approx. %)', '累计销售额占比（%）': 'Cumulative sales share (%)', '有成交商品的销售集中度': 'Sales concentration (sold products)', '春（3-5月）': 'Spring (Mar-May)', '夏（6-8月）': 'Summer (Jun-Aug)', '秋（9-11月）': 'Autumn (Sep-Nov)', '冬（12-2月）': 'Winter (Dec-Feb)', '各季节内部销售额占比（%）': 'Within-season sales share (%)', '销售额': 'Sales', '有成交商品数': 'Products sold', '单品平均购买件数': 'Units per product', '平均每件成交价格': 'Average unit price', '2019年8月=100': 'Aug 2019 = 100', '2019年9月指数': 'Sep 2019 index', '单日购买': 'One day', '多日购买': 'Multiple days', '成交客户占比（%）': 'Purchasing customers (%)', '观察期内购买日期数': 'Distinct purchase days', '1-7天': '1-7 days', '8-14天': '8-14 days', '15-30天': '15-30 days', '31-60天': '31-60 days', '61-90天': '61-90 days', '91-180天': '91-180 days', '181天及以上': '181+ days', '占已复购客户的比例（%）': 'Share of observed repeat purchasers (%)', '首次至第二次购买间隔': 'Time to second purchase', '30天': '30 days', '90天': '90 days', '180天': '180 days', '无完整窗口': 'No eligible customers', '按首次观察购买月份划分的复购率\n* 当月仅部分客户满足完整观察窗口': 'Repeat purchase by first-observed purchase month\n* Only some customers have a full observation window', '复购率（%）': 'Repeat-purchase rate (%)', '未知': 'Unknown', '年龄组': 'Age group', '30天复购率（%）': '30-day repeat-purchase rate (%)', '主要首购归属品类': 'Main first-purchase categories', '实际销量': 'Actual units', '验证选中：ARMA': 'Validation-selected: ARMA', '测试MAE最低：SARIMA': 'Lowest test MAE: SARIMA', '每日购买件数': 'Daily units', '2020年测试日期': 'Test dates in 2020'}


def save(fig, name):
    if ENGLISH:
        from matplotlib.text import Text
        for ax in fig.axes:
            for axis in (ax.xaxis, ax.yaxis):
                ticks = axis.get_ticklocs()
                labels = [item.get_text() for item in axis.get_ticklabels()]
                if any(label in TRANSLATIONS for label in labels):
                    axis.set_ticks(ticks, labels=[TRANSLATIONS.get(label, label) for label in labels])
        for item in fig.findobj(Text):
            item.set_text(TRANSLATIONS.get(item.get_text(), item.get_text()))
    fig.tight_layout(pad=1.5)
    fig.savefig(OUT / name, facecolor="white", bbox_inches="tight")
    plt.close(fig)


monthly = pd.read_csv(R / "monthly_overall_performance.csv")
x = np.arange(len(monthly))
fig, axes = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True)
for ax, col, scale, title, color in [
    (axes[0], "sale_per_month", 1000, "月度销售额（标准化金额，千）", BLUE),
    (axes[1], "units_sold", 10000, "月度购买件数（万件）", TEAL),
]:
    ax.plot(x, monthly[col] / scale, color=color, marker="o", markersize=3)
    ax.scatter([0, 24], monthly[col].iloc[[0, 24]] / scale, s=55,
               facecolor="white", edgecolor=ORANGE, zorder=5, label="不完整月份")
    ax.set_title(title, loc="left", fontsize=11)
    ax.grid(axis="y", alpha=.18)
axes[0].legend(fontsize=9, loc="upper right")
axes[1].set_xticks(x[::3], monthly.month.iloc[::3], rotation=25)
save(fig, "01_monthly_sales.png")

channel = pd.read_csv(R / "monthly_channel_performance.csv")
shares = channel.pivot(index="month", columns="sales_channel_id", values="sales_channel_share").reindex(monthly.month)
# Zero denotes no channel-month transaction row in the export; do not fill the original growth-rate column.
shares = shares.fillna(0)
fig, ax = plt.subplots(figsize=(10, 3.6))
ax.stackplot(x, shares[1], shares[2], colors=[TEAL, BLUE], labels=["渠道1", "渠道2"], alpha=.9)
ax.set(ylim=(0, 100), ylabel="当月销售额占比（%）")
ax.set_xticks(x[::3], monthly.month.iloc[::3], rotation=25)
ax.legend(loc="lower left", ncol=2)
ax.annotate("渠道1无记录", xy=(19, 98), xytext=(15.5, 72),
            arrowprops={"arrowstyle": "->", "color": ORANGE}, color="#202e3c",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": .95, "pad": 4})
save(fig, "02_channel_share.png")

groups = pd.read_csv(P / "category_sales_structure.csv").drop_duplicates("product_group_name").head(7)
labels = {"Garment Upper body": "上身服装", "Garment Lower body": "下身服装",
          "Garment Full body": "全身服装", "Swimwear": "泳装", "Underwear": "内衣",
          "Shoes": "鞋类", "Accessories": "配饰", "Nightwear": "睡衣"}
concentration = pd.read_csv(P / "product_sales_concentration.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
bars = axes[0].barh(groups.product_group_name.map(labels), groups.group_sale_perc, color=BLUE)
axes[0].invert_yaxis()
axes[0].bar_label(bars, fmt="%.2f%%", padding=3, fontsize=9)
axes[0].set(xlim=(0, 47), xlabel="整体销售额占比（%）", title="主要大类销售构成")
axes[1].plot(np.r_[0, concentration.decile * 10], np.r_[0, concentration.cum_sales_pct], marker="o", color=TEAL)
axes[1].plot([0, 100], [0, 100], linestyle="--", color="#b7c0c7", linewidth=1)
axes[1].annotate("前10%贡献61.67%", (10, 61.67), xytext=(23, 47), fontsize=9,
                 arrowprops={"arrowstyle": "->", "color": BLUE})
axes[1].set(xlabel="销售额排名靠前的商品比例（约%）", ylabel="累计销售额占比（%）", title="有成交商品的销售集中度", xlim=(0, 100), ylim=(0, 105))
save(fig, "03_category_concentration.png")

season = pd.read_csv(P / "seasonal_category_sales_structure.csv").drop_duplicates(["season", "product_group_name"])
matrix = season.pivot(index="product_group_name", columns="season", values="group_pct_of_season").reindex(
    index=["Garment Upper body", "Garment Lower body", "Garment Full body", "Swimwear"],
    columns=["Spring", "Summer", "Autumn", "Winter"])
fig, ax = plt.subplots(figsize=(9, 3.2))
im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=55, aspect="auto")
ax.set_xticks(range(4), ["春（3-5月）", "夏（6-8月）", "秋（9-11月）", "冬（12-2月）"])
ax.set_yticks(range(4), [labels[i] for i in matrix.index])
for i in range(4):
    for j in range(4):
        ax.text(j, i, f"{matrix.iloc[i,j]:.2f}%", ha="center", va="center",
                color="white" if matrix.iloc[i,j] > 35 else "#172e44")
fig.colorbar(im, ax=ax, label="各季节内部销售额占比（%）")
save(fig, "04_seasonal_mix.png")

types = pd.read_csv(P / "monthly_product_type_performance.csv")
sweater = types[types.product_type_name.eq("Sweater") & types.month.isin(["2019-08", "2019-09"])].set_index("month")
cols = ["sales", "articles_sold", "units_per_article", "avg_price"]
ratio = sweater.loc["2019-09", cols].astype(float) / sweater.loc["2019-08", cols].astype(float) * 100
fig, ax = plt.subplots(figsize=(9, 3.4))
bars = ax.bar(["销售额", "有成交商品数", "单品平均购买件数", "平均每件成交价格"], ratio, color=[BLUE, TEAL, TEAL, TEAL], width=.58)
ax.axhline(100, linestyle="--", color=ORANGE, label="2019年8月=100")
ax.bar_label(bars, fmt="%.1f", padding=3)
ax.set(ylabel="2019年9月指数", ylim=(0, 330))
ax.legend(loc="upper right")
save(fig, "05_sweater_growth.png")

interval = pd.read_csv(R / "second_purchase_interval_distribution.csv")
fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), gridspec_kw={"width_ratios": [1, 1.65]})
bars = axes[0].bar(["单日购买", "多日购买"], [32.88, 67.12], color=["#a5b5c1", BLUE])
axes[0].bar_label(bars, fmt="%.2f%%", padding=3)
axes[0].set(ylim=(0, 80), ylabel="成交客户占比（%）", title="观察期内购买日期数")
bars = axes[1].barh(["1-7天", "8-14天", "15-30天", "31-60天", "61-90天", "91-180天", "181天及以上"], interval.customer_pct, color=TEAL)
axes[1].bar_label(bars, fmt="%.2f%%", padding=3, fontsize=9)
axes[1].invert_yaxis()
axes[1].set(xlim=(0, 24), xlabel="占已复购客户的比例（%）", title="首次至第二次购买间隔")
save(fig, "06_repurchase_overview.png")

cohort = pd.read_csv(R / "monthly_cohort_repurchase_rates.csv")
matrix = cohort[["repeat_30d_pct", "repeat_90d_pct", "repeat_180d_pct"]].to_numpy(float)
fig, ax = plt.subplots(figsize=(8.2, 8))
cmap = plt.get_cmap("YlGnBu").copy()
cmap.set_bad("#eeeeee")
im = ax.imshow(np.ma.masked_invalid(matrix), aspect="auto", cmap=cmap, vmin=0, vmax=80)
ax.set_xticks(range(3), ["30天", "90天", "180天"])
ax.set_yticks(range(len(cohort)), cohort.first_purchase_month, fontsize=9)
for i in range(len(cohort)):
    for j, days in enumerate([30, 90, 180]):
        val = matrix[i, j]
        eligible = cohort.iloc[i][f"eligible_customers_{days}d"]
        partial = 0 < eligible < cohort.iloc[i].cohort_customers
        label = "无完整窗口" if np.isnan(val) else f"{val:.2f}%" + (" *" if partial else "")
        ax.text(j, i, label, ha="center", va="center", fontsize=8,
                color="white" if np.isfinite(val) and val > 48 else "#1d3348")
ax.set_title("按首次观察购买月份划分的复购率\n* 当月仅部分客户满足完整观察窗口", fontsize=11)
fig.colorbar(im, ax=ax, label="复购率（%）", fraction=.04, pad=.04)
save(fig, "07_cohort_repurchase.png")

age = pd.read_csv(R / "age_group_30d_repurchase.csv").set_index("age_group").reindex(["<25", "25-34", "35-44", "45-54", "55+", "unknown"])
cat = pd.read_csv(R / "first_category_30d_repurchase.csv")
cat = cat[cat.first_group.isin(labels)].sort_values("repeat_30d_pct", ascending=False)
fig, axes = plt.subplots(1, 2, figsize=(10, 4.1))
bars = axes[0].barh(["<25", "25-34", "35-44", "45-54", "55+", "未知"], age.repeat_30d_pct, color=BLUE)
axes[0].bar_label(bars, fmt="%.2f%%", padding=3, fontsize=8)
axes[0].invert_yaxis()
axes[0].set(title="年龄组", xlim=(0, 37), xlabel="30天复购率（%）")
bars = axes[1].barh(cat.first_group.map(labels), cat.repeat_30d_pct, color=TEAL)
axes[1].bar_label(bars, fmt="%.2f%%", padding=3, fontsize=8)
axes[1].invert_yaxis()
axes[1].set(title="主要首购归属品类", xlim=(0, 37), xlabel="30天复购率（%）")
save(fig, "08_segment_repurchase.png")

forecast = pd.read_csv(ROOT / "forecasting/results/run_02/test_actual_vs_forecast.csv", parse_dates=["date"])
fig, ax = plt.subplots(figsize=(10, 4))
for col, label, color in [("actual", "实际销量", "#172b3e"), ("ARMA11", "验证选中：ARMA", ORANGE), ("SARIMA111_011_7", "测试MAE最低：SARIMA", TEAL)]:
    ax.plot(forecast.date, forecast[col], label=label, color=color, linewidth=1.8)
ax.set(ylabel="每日购买件数", xlabel="2020年测试日期")
ax.grid(axis="y", alpha=.2)
ax.legend(fontsize=9, loc="lower left")
save(fig, "09_actual_vs_selected.png")
print(f"已生成{len(list(OUT.glob('*.png')))}张SQL与综合预测图：{OUT}")
