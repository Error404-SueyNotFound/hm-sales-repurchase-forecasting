"""Build the results index and a local ZIP from an explicit file allowlist.
Exclude raw transaction/customer data and local environments.
This script does not publish a repository; rerunning updates the local archive."""
from pathlib import Path
import csv
import hashlib
import json
import re
import zipfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEST = ROOT / "deliverables"
DEST.mkdir(exist_ok=True)
names = {
    "dq_01_id_uniqueness": "商品/客户编号唯一性", "dq_02_empty_ids": "空字符串编号检查",
    "dq_03_reference_integrity": "交易关联完整性", "dq_05_age": "年龄缺失与范围",
    "dq_06_date_coverage": "日期覆盖连续性", "dq_07_sales_channels": "渠道规模",
    "monthly_overall_performance": "全渠道月度销售", "monthly_channel_performance": "分渠道月度销售",
    "category_sales_structure": "整体品类销售结构", "seasonal_category_sales_structure": "季节品类销售结构",
    "monthly_category_sales_structure": "月度品类销售结构", "channel_category_sales_structure": "分渠道品类结构",
    "product_sales_concentration": "商品销售集中度", "top_decile_product_category_mix": "头部10%商品品类构成",
    "monthly_product_type_performance": "细分类月度表现", "customer_repurchase_overview": "单日与多日购买客户",
    "second_purchase_interval_summary": "二次购买间隔均值与中位数", "second_purchase_interval_distribution": "二次购买间隔分布",
    "customer_repurchase_rates": "30/90/180天复购率", "monthly_cohort_repurchase_rates": "首购月份客户群复购率",
    "first_category_30d_repurchase": "首购品类30天复购率", "first_channel_30d_repurchase": "首购渠道30天复购率",
    "age_group_30d_repurchase": "年龄组30天复购率", "new_returning_customer_contribution": "首购日与后续购买贡献",
}
lines = ["# 结果文件索引与主要字段", "", "本索引基于2026-11-09整理的已保存文件。SQL结果24份；Python主要分析使用run_02。", "",
         "## SQL结果", "", "每个链接对应实际CSV。行数不含表头；报表中的total行属于结果行，不要重复计入总数。", ""]
sql_files = sorted((ROOT / "results").rglob("*.csv"))
assert len(sql_files) == 24
for f in sql_files:
    with f.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        headers = next(reader)
        count = sum(1 for _ in reader)
    title = names.get(f.stem, f.stem)
    lines += [f"### {title}", "", f"[{f.name}](../{f.relative_to(ROOT).as_posix()})：{count}行。", "",
              "字段：" + "、".join(f"`{x}`" for x in headers) + "。", ""]
lines += ["## 主要字段口径", "", "| 字段 | 含义 |", "|---|---|"]
for field, meaning in [
    ("sale_per_month / sales / type_sale", "对应粒度的标准化销售额，不是货币金额或利润"),
    ("customer_per_month", "当月去重购买客户，不能跨渠道或跨月直接求和为总客户"),
    ("units_sold / unit_sold / units", "购买记录件数，不是订单数"),
    ("spend_per_customer", "销售额÷去重购买客户数，不是客单价"),
    ("unit_per_customer", "购买件数÷去重购买客户数"),
    ("month_growth_rate / *_growth_rate", "与上一条月份记录比较；缺月时不是普通环比"),
    ("sales_channel_share", "当前渠道销售额÷当月全部渠道销售额×100"),
    ("group_sale", "大类金额，在多条细分类行重复，不能整列直接求和"),
    ("type_sale_group_perc / type_pct_of_group", "细分类金额÷所属大类金额×100"),
    ("type_sale_total_perc", "细分类金额÷当前查询定义的总体销售额×100；注意是否含月份/渠道分组"),
    ("articles_sold", "有成交的不同商品编号数，不是全部上架商品数"),
    ("units_per_article", "件数÷有成交商品数，不是库存周转率"),
    ("avg_price", "销售额÷购买件数，为标准化平均成交价格"),
    ("decile", "有成交商品按销售额降序划分的十分位组，1为头部"),
    ("sale_pec / cum_sales_pct", "十分位组销售额占比 / 截至该组累计占比"),
    ("pct_of_top10_sales", "该品类头部商品金额÷所有头部10%商品金额×100"),
    ("cohort_customers", "首次观察购买发生在该月的客户数"),
    ("eligible_customers_30d/90d/180d", "有完整对应后续观察窗口的客户数"),
    ("repeat_customers_30d", "合格客户中首购后1-30天跨日期再次购买的人数"),
    ("repeat_30d_pct/90d_pct/180d_pct", "合格客户中的对应期限累计复购率，100表示100%"),
    ("avg_days / median_days", "已观察到复购客户的首次至第二次购买间隔均值 / 中位数"),
    ("customer_pct（间隔表）", "该间隔组人数÷已复购客户总人数×100"),
    ("customer_type", "new为首次观察购买日，existing为该客户之后日期的交易"),
    ("units_pct / sales_pct", "该交易归属的件数 / 标准化销售额占总体的比例"),
]:
    lines.append(f"| `{field}` | {meaning} |")
lines += ["", "## Python结果（run_02）", "", "文件用途与模型设置详见[预测说明](../forecasting/README.md)。", ""]
for f in sorted((ROOT / "forecasting/results/run_02").glob("*.csv")):
    with f.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        headers = next(reader)
        count = sum(1 for _ in reader)
    lines += [f"- [{f.name}](../{f.relative_to(ROOT).as_posix()})：{count}行；字段：" + "、".join(f"`{h}`" for h in headers) + "。"]
lines += ["", "## 阅读顺序", "", "先看完整项目报告，再按图表来源打开CSV；需要检查计算逻辑时返回对应SQL或Python。完整报告只展示主要发现，逐表说明保留在SQL分析报告中。", "",
          "缺失的直接导出：数据质量日期/价格检查、复购客户基础表唯一性核验、原始交易总量核验。这些没有伪造补充文件；主要总量使用其他已保存表交叉核对。", ""]
(REPORTS / "结果文件索引.md").write_text("\n".join(lines), encoding="utf-8")

# Include only whitelisted code, aggregate results, charts, and reports.
files = [ROOT / "README.md", ROOT / ".gitignore"]
for folder in ["code", "results", "reports", "reporting"]:
    files += [p for p in (ROOT / folder).rglob("*") if p.is_file()
              and "__pycache__" not in p.parts
              and p.suffix in {".sql", ".csv", ".md", ".pdf", ".png", ".json", ".py"}]
files += [p for p in (ROOT / "forecasting").iterdir()
          if p.is_file() and p.suffix in {".py", ".txt", ".md", ".csv"}]
for run in ["run_01", "run_02"]:
    files += [p for p in (ROOT / "forecasting/results" / run).iterdir()
              if p.is_file() and p.suffix in {".csv", ".json", ".md", ".png", ".txt"}]
files = sorted(p for p in set(files) if p.name != "简历与面试准备.md")
assert not any(".venv" in p.parts or p.name in {"customers.csv", "articles.csv", "transactions_train.csv"} for p in files)

# Check local Markdown links, including images, before building the delivery archive.
allowed = {p.resolve() for p in files}
broken = []
for p in files:
    if p.suffix != ".md":
        continue
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "#")):
            continue
        resolved = (p.parent / unquote(target.split("#")[0])).resolve()
        if resolved not in allowed:
            broken.append((str(p.relative_to(ROOT)), target))
if broken:
    raise ValueError(f"发现未打包或失效链接：{broken}")

manifest = {"project": "H&M sales, repurchase and historical forecasting",
            "as_of": "2026-11-09", "files": []}
for p in files:
    manifest["files"].append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
                              "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
archive = DEST / "HM_SQL_Python_完整项目.zip"
prefix = "hm-sales-repurchase-forecasting"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for p in files:
        bundle.write(p, prefix + "/" + p.relative_to(ROOT).as_posix())
    bundle.writestr(prefix + "/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    assert len(bundle.namelist()) == len(files) + 1
    for p in files:
        stored = bundle.read(prefix + "/" + p.relative_to(ROOT).as_posix())
        assert hashlib.sha256(stored).hexdigest() == hashlib.sha256(p.read_bytes()).hexdigest()
print(f"打包与链接检查通过：{len(files)}个项目文件，{archive.stat().st_size / 1024 / 1024:.2f} MiB")
print(archive)
