#!/usr/bin/env python3
"""
Generate styled PDF from Markdown race report.
Design system: dark header + orange accent + layered blockquotes.
"""

import markdown
import re
from weasyprint import HTML

import sys

# Allow command-line override: python generate_pdf.py <md_file> <pdf_file>
if len(sys.argv) >= 3:
    MD_FILE = sys.argv[1]
    PDF_FILE = sys.argv[2]
elif len(sys.argv) == 2:
    MD_FILE = sys.argv[1]
    PDF_FILE = MD_FILE.replace('.md', '.pdf')
else:
    MD_FILE = 'example_report.md'
    PDF_FILE = 'example_report.pdf'

# ── Read markdown ──────────────────────────────────────────────
with open(MD_FILE, 'r', encoding='utf-8') as f:
    md_text = f.read()

# ── Convert markdown → HTML ───────────────────────────────────
html_body = markdown.markdown(
    md_text,
    extensions=['tables', 'fenced_code', 'nl2br'],
)

# ── Post-process HTML to add semantic classes ─────────────────

# 1. Classify blockquotes by content keywords
def classify_blockquote(match):
    content = match.group(1)
    if any(kw in content for kw in ['长期建议', '目的', '注意', '核心认知更新']):
        css_class = 'note-info'
    elif any(kw in content for kw in ['红灯', '停跑', '感染', '禁止', '严禁']):
        css_class = 'note-danger'
    elif any(kw in content for kw in ['⭐', '关键', '决定', '重要', '必须', '结果会直接']):
        css_class = 'note-warning'
    elif any(kw in content for kw in ['本报告', '天气数据', '生成于']):
        css_class = 'note-meta'
    else:
        css_class = 'note-info'
    return f'<blockquote class="{css_class}">{content}</blockquote>'

html_body = re.sub(
    r'<blockquote>(.*?)</blockquote>',
    classify_blockquote,
    html_body,
    flags=re.DOTALL,
)

# 2. Wrap the title section (first h1) with a banner div
html_body = re.sub(
    r'<h1>(.*?)</h1>',
    r'<div class="title-banner"><h1>\1</h1></div>',
    html_body,
    count=1,
)

# 3. Add accent class to Part dividers (h1 that contains "Part")
html_body = re.sub(
    r'<h1>(Part\s.*?)</h1>',
    r'<div class="part-banner"><h1>\1</h1></div>',
    html_body,
)

# 4. Wrap lock-screen memo section (h1 + everything after it) in a single-page div
html_body = re.sub(
    r'<h1>([^<]*锁屏备忘[^<]*)</h1>(.*)',
    r'<div class="lockscreen-section"><h1 class="lockscreen-title">\1</h1>\2</div>',
    html_body,
    flags=re.DOTALL,
)

# 5. Style horizontal rules as orange accent bars
html_body = html_body.replace('<hr />', '<div class="accent-bar"></div>')
html_body = html_body.replace('<hr>', '<div class="accent-bar"></div>')

# 5. Highlight key metric values with orange (numbers with units like 1:33:00, 4'22", +92", etc)
# Only in table cells
def highlight_table_values(match):
    cell_content = match.group(1)
    # Highlight times like 1:33:00, 1:36:03
    cell_content = re.sub(
        r'\b(\d:\d{2}:\d{2})\b',
        r'<span class="metric-value">\1</span>',
        cell_content,
    )
    return f'<td>{cell_content}</td>'

# ── Full HTML document ────────────────────────────────────────
full_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
/* ═══════════════════════════════════════════════════════════
   Design System — Marathon Copilot Report Style
   ═══════════════════════════════════════════════════════════ */

/* ── Page Setup ─────────────────────────────────────────── */
@page {{
    size: A4;
    margin: 1.8cm 2cm;
    @bottom-center {{
        content: counter(page);
        font-size: 9pt;
        color: #999;
    }}
}}

/* ── Base Typography ────────────────────────────────────── */
body {{
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: #1a1a1a;
    background: #ffffff;
}}

/* ── Title Banner ───────────────────────────────────────── */
.title-banner {{
    background: #2c3e50;
    color: #ffffff;
    padding: 18px 24px 14px;
    margin: -10px -10px 20px;
    border-radius: 4px;
}}
.title-banner h1 {{
    font-size: 20pt;
    font-weight: bold;
    color: #ffffff;
    margin: 0;
    padding: 0;
    border: none;
    letter-spacing: 1px;
}}

/* ── Part Banners ───────────────────────────────────────── */
.part-banner {{
    background: linear-gradient(135deg, #34495e, #2c3e50);
    color: #ffffff;
    padding: 12px 20px 10px;
    margin: 28px -10px 18px;
    border-radius: 4px;
    page-break-before: auto;
}}
.part-banner h1 {{
    font-size: 14pt;
    font-weight: bold;
    color: #ffffff;
    margin: 0;
    padding: 0;
    border: none;
    letter-spacing: 0.5px;
}}

/* ── Section Headers ────────────────────────────────────── */
h2 {{
    font-size: 14pt;
    font-weight: bold;
    color: #2c3e50;
    border-bottom: 2.5px solid #2c3e50;
    padding-bottom: 6px;
    margin-top: 26px;
    margin-bottom: 12px;
}}

h3 {{
    font-size: 12pt;
    font-weight: bold;
    color: #34495e;
    margin-top: 20px;
    margin-bottom: 8px;
    padding-left: 10px;
    border-left: 3.5px solid #e67e22;
}}

h4 {{
    font-size: 11pt;
    font-weight: bold;
    color: #34495e;
    margin-top: 16px;
    margin-bottom: 6px;
}}

/* ── Orange Accent Bar (replaces <hr>) ──────────────────── */
.accent-bar {{
    height: 3px;
    background: linear-gradient(90deg, #e67e22, #f39c12);
    border: none;
    margin: 24px 0;
    border-radius: 2px;
}}

/* ── Tables ─────────────────────────────────────────────── */
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0 16px;
    font-size: 9pt;
    border: none;
    border-radius: 4px;
    overflow: hidden;
}}

thead th,
tr:first-child th {{
    background: #2c3e50;
    color: #ffffff;
    font-weight: bold;
    padding: 8px 10px;
    text-align: left;
    border: none;
    font-size: 9pt;
}}

/* Handle tables without thead — first row as header */
table tr:first-child td {{
    /* Will be overridden for non-header tables */
}}

td, th {{
    padding: 7px 10px;
    border-bottom: 1px solid #e8e8e8;
    text-align: left;
    vertical-align: top;
}}

/* Alternating row backgrounds */
tbody tr:nth-child(even),
tr:nth-child(even) {{
    background: #f8f9fa;
}}

tbody tr:nth-child(odd),
tr:nth-child(odd) {{
    background: #ffffff;
}}

/* First row override - always dark header style for markdown tables */
table tr:first-child {{
    background: #2c3e50 !important;
}}
table tr:first-child th,
table tr:first-child td {{
    background: #2c3e50;
    color: #ffffff;
    font-weight: bold;
    border: none;
}}

/* Second row is often the markdown separator row, skip its style — 
   but markdown extension converts it properly so tr:nth-child counts from data rows */

/* ── Blockquote / Note Boxes ────────────────────────────── */
blockquote {{
    margin: 14px 0;
    padding: 12px 16px;
    border-radius: 4px;
    font-size: 10pt;
    line-height: 1.65;
    border-left: 4px solid;
    page-break-inside: avoid;
}}

blockquote.note-info {{
    background: #e9f2f8;
    border-left-color: #3498db;
    color: #1a3a5c;
}}

blockquote.note-warning {{
    background: #fdf2e8;
    border-left-color: #e67e22;
    color: #5a3510;
}}

blockquote.note-danger {{
    background: #fdedeb;
    border-left-color: #c0392b;
    color: #5a1a15;
}}

blockquote.note-meta {{
    background: #f5f5f5;
    border-left-color: #999;
    color: #666;
    font-size: 9pt;
}}

/* ── Code Blocks ────────────────────────────────────────── */
pre {{
    background: #f0f3f6;
    border: 1px solid #dce1e6;
    border-radius: 4px;
    padding: 14px 16px;
    font-family: "Noto Sans Mono CJK SC", "Consolas", "Monaco", monospace;
    font-size: 9pt;
    line-height: 1.55;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: #2c3e50;
}}

code {{
    font-family: "Noto Sans Mono CJK SC", "Consolas", "Monaco", monospace;
    font-size: 9pt;
    background: #f0f3f6;
    padding: 2px 5px;
    border-radius: 3px;
    color: #c0392b;
}}

pre code {{
    background: none;
    padding: 0;
    color: #2c3e50;
}}

/* ── Inline Emphasis ────────────────────────────────────── */
strong {{
    color: #2c3e50;
    font-weight: bold;
}}

/* Orange highlight for key metrics in bold */
em {{
    font-style: italic;
    color: #34495e;
}}

/* ── Lists ──────────────────────────────────────────────── */
ul, ol {{
    margin: 8px 0;
    padding-left: 24px;
}}

li {{
    margin-bottom: 4px;
    line-height: 1.65;
}}

li strong {{
    color: #2c3e50;
}}

/* ── Paragraphs ─────────────────────────────────────────── */
p {{
    margin: 8px 0;
    line-height: 1.7;
}}

/* ── Star highlights ────────────────────────────────────── */
/* Make ⭐ content slightly larger */

/* ── Print optimizations ────────────────────────────────── */
h2, h3, h4 {{
    page-break-after: avoid;
}}

table {{
    page-break-inside: auto;
}}

tr {{
    page-break-inside: avoid;
}}

blockquote {{
    page-break-inside: avoid;
}}

/* ── Special sections ───────────────────────────────────── */
/* Lock-screen memo: force entire section onto one page, compact layout */
.lockscreen-section {{
    page-break-before: always;
    page-break-inside: avoid;
    padding: 0;
}}
.lockscreen-section .lockscreen-title {{
    font-size: 15pt;
    font-weight: bold;
    color: #2c3e50;
    border-bottom: 2.5px solid #e67e22;
    padding-bottom: 5px;
    margin-top: 0;
    margin-bottom: 8px;
}}
.lockscreen-section p {{
    font-size: 9pt;
    line-height: 1.45;
    margin: 3px 0;
}}
.lockscreen-section ul {{
    margin: 4px 0;
    padding-left: 18px;
}}
.lockscreen-section li {{
    font-size: 9pt;
    line-height: 1.45;
    margin-bottom: 3px;
}}
/* Plan A/B/C labels */

</style>
</head>
<body>
{html_body}
</body>
</html>'''

# ── Generate PDF ──────────────────────────────────────────────
HTML(string=full_html).write_pdf(PDF_FILE)

import os
size = os.path.getsize(PDF_FILE)
print(f'PDF generated: {PDF_FILE} ({size/1024:.0f} KB)')

# Count pages
import fitz
doc = fitz.open(PDF_FILE)
print(f'Pages: {len(doc)}')
doc.close()
