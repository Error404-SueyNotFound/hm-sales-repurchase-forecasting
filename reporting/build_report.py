"""Render Chinese or English PDFs from the user-edited Markdown source.

Set HM_REPORT_LANGUAGE=en for English. Never overwrite the Markdown source.
Requires reportlab, pypdf and macOS Chinese fonts.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.utils import ImageReader

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
pdfmetrics.registerFont(TTFont("CN", "/System/Library/Fonts/STHeiti Light.ttc", subfontIndex=0))
pdfmetrics.registerFont(TTFont("CNBold", "/System/Library/Fonts/STHeiti Medium.ttc", subfontIndex=0))
pdfmetrics.registerFontFamily("CN", normal="CN", bold="CNBold", italic="CN", boldItalic="CNBold")
NAVY, BLUE, TEAL = colors.HexColor("#173249"), colors.HexColor("#23658c"), colors.HexColor("#218c86")
styles = {
    "title": ParagraphStyle("title", fontName="CNBold", fontSize=22, leading=29, textColor=NAVY, spaceAfter=16, wordWrap="CJK"),
    "kicker": ParagraphStyle("kicker", fontName="Helvetica", fontSize=9, leading=13, textColor=TEAL, spaceAfter=8),
    "body": ParagraphStyle("body", fontName="CN", fontSize=10, leading=16, textColor=NAVY, spaceAfter=9, wordWrap="CJK"),
    "h2": ParagraphStyle("h2", fontName="CNBold", fontSize=12, leading=18, textColor=BLUE, spaceBefore=6, spaceAfter=8, wordWrap="CJK"),
    "note": ParagraphStyle("note", fontName="CN", fontSize=8, leading=12, textColor=colors.HexColor("#596b78"), spaceAfter=8, wordWrap="CJK"),
    "cell": ParagraphStyle("cell", fontName="CN", fontSize=8.6, leading=12, textColor=NAVY, wordWrap="CJK"),
    "th": ParagraphStyle("th", fontName="CNBold", fontSize=8.6, leading=12, textColor=colors.white, wordWrap="CJK"),
}


def text(value): return {"kind": "text", "text": value}
def note(value): return {"kind": "note", "text": value}
def heading(value): return {"kind": "heading", "text": value}
def table(headers, rows, widths=None): return {"kind": "table", "headers": headers, "rows": rows, "widths": widths}
def chart(name, caption, height=220): return {"kind": "image", "path": "figures/" + name, "caption": caption, "height": height}
def page(kicker, title, blocks): return {"kicker": kicker, "title": title, "blocks": blocks}


def parse_report(path):
    """Read headings, tables, images and paragraphs without rewriting Markdown."""
    import re
    layout = json.loads((REPORTS / "report_structure.json").read_text())
    rows = path.read_text().splitlines()
    parsed, section, i = [], None, 0
    while i < len(rows):
        line = rows[i].strip()
        if line.startswith("## "):
            section = {"title": line[3:], "kicker": layout[len(parsed)]["kicker"], "blocks": []}
            parsed.append(section); i += 1; continue
        if section is None or not line:
            i += 1; continue
        if line.startswith("### "):
            section["blocks"].append(heading(line[4:])); i += 1; continue
        match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
        if match:
            old_images = [b for b in layout[len(parsed)-1]["blocks"] if b["kind"] == "image"]
            old = next((b for b in old_images if Path(b["path"]).name == Path(match[2]).name), old_images[0])
            section["blocks"].append({"kind":"image", "path":match[2], "caption":match[1], "height":old["height"]})
            i += 1
            while i < len(rows) and not rows[i].strip(): i += 1
            if i < len(rows) and rows[i].strip() == match[1]: i += 1
            continue
        if line.startswith("|"):
            cells=[]
            while i < len(rows) and rows[i].strip().startswith("|"):
                row=[v.strip() for v in rows[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?",v) for v in row): cells.append(row)
                i += 1
            table_idx=sum(b["kind"] == "table" for b in section["blocks"])
            old=[b for b in layout[len(parsed)-1]["blocks"] if b["kind"] == "table"][table_idx]
            section["blocks"].append(table(cells[0],cells[1:],old["widths"])); continue
        para=[]
        while i<len(rows) and rows[i].strip() and not rows[i].startswith(("## ","### ","|","![")):
            para.append(rows[i].strip()); i+=1
        section["blocks"].append(text("\n".join(para)))
    assert len(parsed)==12
    for section in parsed:
        if section["blocks"][-1]["kind"]=="text": section["blocks"][-1]["kind"]="note"
    return parsed


import os
ENGLISH = os.environ.get("HM_REPORT_LANGUAGE", "zh") == "en"
source_md = REPORTS / ("HM_Project_Report_EN.md" if ENGLISH else "HM_完整项目报告.md")
source_bytes = source_md.read_bytes()
if ENGLISH:
    for key, style in styles.items():
        style.fontName = "Helvetica-Bold" if key in {"title","h2","th"} else "Helvetica"
        style.wordWrap = None
    styles["title"].fontSize=18; styles["title"].leading=23
    styles["body"].fontSize=9.4; styles["body"].leading=13.5
    styles["cell"].fontSize=8; styles["cell"].leading=11
    styles["th"].fontSize=8; styles["th"].leading=11
pages = parse_report(source_md)


def paragraph(value, style="body"):
    return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])


WIDTH = A4[0] - 88
story = []
markdown = ["# H&M 销售、客户复购与销量预测", "", "完整项目报告 | 2026-11-09", ""]
for index, section in enumerate(pages):
    if index:
        story.append(PageBreak())
    story.extend([paragraph(section["kicker"], "kicker"), paragraph(section["title"], "title")])
    markdown += ["## " + section["title"], ""]
    for block in section["blocks"]:
        kind = block["kind"]
        if kind in {"text", "note", "heading"}:
            style = {"text": "body", "note": "note", "heading": "h2"}[kind]
            story.append(paragraph(block["text"], style))
            markdown += [("### " if kind == "heading" else "") + block["text"], ""]
        elif kind == "image":
            path = REPORTS / block["path"]
            w, h = ImageReader(str(path)).getSize()
            scale = min(WIDTH / w, block["height"] / h)
            story += [Image(str(path), width=w * scale, height=h * scale), Spacer(1, 5), paragraph(block["caption"], "note")]
            markdown += [f"![{block['caption']}]({block['path']})", "", block["caption"], ""]
        elif kind == "table":
            widths = block["widths"] or [1 / len(block["headers"])] * len(block["headers"])
            rows = [[paragraph(v, "th") for v in block["headers"]]]
            rows += [[paragraph(v, "cell") for v in row] for row in block["rows"]]
            t = Table(rows, colWidths=[WIDTH * w for w in widths], repeatRows=1, hAlign="LEFT")
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0f5f7"), colors.white]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, -1), (-1, -1), .5, colors.HexColor("#ced9df")),
            ]))
            story += [t, Spacer(1, 11)]
            markdown += ["| " + " | ".join(block["headers"]) + " |", "| " + " | ".join(["---"] * len(block["headers"])) + " |"]
            markdown += ["| " + " | ".join(row) + " |" for row in block["rows"]] + [""]


def decorate(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(2)
    canvas.line(44, A4[1] - 26, A4[0] - 44, A4[1] - 26)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#657988"))
    canvas.drawString(44, 24, "H&M | SQL + PYTHON | HISTORICAL ANALYSIS")
    canvas.drawRightString(A4[0] - 44, 24, f"{doc.page:02d}")
    canvas.restoreState()


pdf_path = source_md.with_suffix(".pdf")
doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, rightMargin=44, leftMargin=44,
                        topMargin=43, bottomMargin=45, title="H&M Sales, Repeat Purchase and Forecasting" if ENGLISH else pages[0]["title"], author="H&M SQL / Python Project")
doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
assert source_md.read_bytes() == source_bytes, "Do not overwrite user-edited Markdown."
(REPORTS / ("report_structure_en.json" if ENGLISH else "report_structure.json")).write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")
from pypdf import PdfReader
reader = PdfReader(pdf_path)
assert len(reader.pages) == len(pages), f"版面溢出：预期{len(pages)}页，实际{len(reader.pages)}页"
assert all(len(p.extract_text().strip()) > 100 for p in reader.pages)
print(f"报告已生成并通过页数/文本检查：{len(reader.pages)}页，{pdf_path}")
