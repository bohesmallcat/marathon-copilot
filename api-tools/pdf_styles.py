"""
pdf_styles.py — Shared CSS design system and HTML post-processing for PDF generation.

Provides a single source of truth for the Marathon Copilot PDF design:
  - Dark header (#2c3e50)
  - Orange accent (#e67e22)
  - Layered blockquotes (info/warning/danger/meta)
  - Table styling with dark header rows

Used by: generate_pdf.py, generate_daily_briefing.py, daily_weather_email.py.
"""

import re


# ═══════════════════════════════════════════════════════════
# CSS Design System
# ═══════════════════════════════════════════════════════════

CSS_DESIGN_SYSTEM = """
@page {
    size: A4;
    margin: 1.8cm 2cm;
    @bottom-center { content: counter(page); font-size: 9pt; color: #999; }
}

body {
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif;
    font-size: 10.5pt; line-height: 1.7; color: #1a1a1a; background: #fff;
}

/* ── Title Banner ───────────────────────────────────────── */
.title-banner {
    background: #2c3e50; color: #fff; padding: 18px 24px 14px;
    margin: -10px -10px 20px; border-radius: 4px;
}
.title-banner h1 {
    font-size: 18pt; font-weight: bold; color: #fff;
    margin: 0; padding: 0; border: none; letter-spacing: 1px;
}

/* ── Part Banners ───────────────────────────────────────── */
.part-banner {
    background: linear-gradient(135deg, #34495e, #2c3e50);
    color: #fff; padding: 12px 20px 10px;
    margin: 28px -10px 18px; border-radius: 4px;
    page-break-before: auto;
}
.part-banner h1 {
    font-size: 14pt; font-weight: bold; color: #fff;
    margin: 0; padding: 0; border: none; letter-spacing: 0.5px;
}

/* ── Section Headers ────────────────────────────────────── */
h2 {
    font-size: 14pt; font-weight: bold; color: #2c3e50;
    border-bottom: 2.5px solid #2c3e50; padding-bottom: 6px;
    margin-top: 26px; margin-bottom: 12px;
}
h3 {
    font-size: 12pt; font-weight: bold; color: #34495e;
    margin-top: 20px; margin-bottom: 8px;
    padding-left: 10px; border-left: 3.5px solid #e67e22;
}
h4 {
    font-size: 11pt; font-weight: bold; color: #34495e;
    margin-top: 16px; margin-bottom: 6px;
}

/* ── Orange Accent Bar (replaces <hr>) ──────────────────── */
.accent-bar {
    height: 3px;
    background: linear-gradient(90deg, #e67e22, #f39c12);
    border: none; margin: 24px 0; border-radius: 2px;
}

/* ── Tables ─────────────────────────────────────────────── */
table {
    border-collapse: collapse; width: 100%; margin: 12px 0 16px;
    font-size: 9pt; border: none; border-radius: 4px; overflow: hidden;
}
table tr:first-child { background: #2c3e50 !important; }
table tr:first-child th, table tr:first-child td {
    background: #2c3e50; color: #fff; font-weight: bold; border: none;
}
th, td {
    padding: 7px 10px; border-bottom: 1px solid #e8e8e8;
    text-align: left; vertical-align: top;
}
tbody tr:nth-child(even), tr:nth-child(even) { background: #f8f9fa; }
tbody tr:nth-child(odd), tr:nth-child(odd)   { background: #fff; }

/* ── Blockquote / Note Boxes ────────────────────────────── */
blockquote {
    margin: 14px 0; padding: 12px 16px; border-radius: 4px;
    font-size: 10pt; line-height: 1.65; border-left: 4px solid;
    page-break-inside: avoid;
}
blockquote.note-info    { background: #e9f2f8; border-left-color: #3498db; color: #1a3a5c; }
blockquote.note-warning { background: #fdf2e8; border-left-color: #e67e22; color: #5a3510; }
blockquote.note-danger  { background: #fdedeb; border-left-color: #c0392b; color: #5a1a15; }
blockquote.note-meta    { background: #f5f5f5; border-left-color: #999; color: #666; font-size: 9pt; }

/* ── Code Blocks ────────────────────────────────────────── */
pre {
    background: #f0f3f6; border: 1px solid #dce1e6; border-radius: 4px;
    padding: 14px 16px; font-family: "Consolas", "Monaco", monospace;
    font-size: 9pt; line-height: 1.55; white-space: pre-wrap; word-wrap: break-word;
    color: #2c3e50;
}
code {
    font-family: "Consolas", "Monaco", monospace; font-size: 9pt;
    background: #f0f3f6; padding: 2px 5px; border-radius: 3px; color: #c0392b;
}
pre code { background: none; padding: 0; color: #2c3e50; }

/* ── Inline Emphasis ────────────────────────────────────── */
strong { color: #2c3e50; }

/* ── Lists ──────────────────────────────────────────────── */
ul, ol { margin: 8px 0; padding-left: 24px; }
li { margin-bottom: 4px; line-height: 1.65; }
p { margin: 8px 0; line-height: 1.7; }

/* ── Print optimizations ────────────────────────────────── */
h2, h3 { page-break-after: avoid; }
table { page-break-inside: auto; }
tr { page-break-inside: avoid; }

/* ── Lock-screen memo (compact single-page) ─────────────── */
.lockscreen-section {
    page-break-before: always; page-break-inside: avoid; padding: 0;
}
.lockscreen-section .lockscreen-title {
    font-size: 15pt; font-weight: bold; color: #2c3e50;
    border-bottom: 2.5px solid #e67e22; padding-bottom: 5px;
    margin-top: 0; margin-bottom: 8px;
}
.lockscreen-section p { font-size: 9pt; line-height: 1.45; margin: 3px 0; }
.lockscreen-section ul { margin: 4px 0; padding-left: 18px; }
.lockscreen-section li { font-size: 9pt; line-height: 1.45; margin-bottom: 3px; }
"""


# ═══════════════════════════════════════════════════════════
# HTML Post-Processing
# ═══════════════════════════════════════════════════════════

# Keywords used to classify blockquote types
_BQ_DANGER_KW = ["红灯", "停跑", "必须降级", "危险", "方案失效"]
_BQ_WARNING_KW = ["注意", "数据获取失败", "⭐", "关键", "重要", "必须", "核心认知更新"]
_BQ_META_KW = ["本报告", "本日报", "天气数据", "生成于"]


def classify_blockquotes(html):
    """Classify <blockquote> elements by content keywords."""
    def _classify(match):
        content = match.group(1)
        if any(k in content for k in _BQ_DANGER_KW):
            cls = "note-danger"
        elif any(k in content for k in _BQ_WARNING_KW):
            cls = "note-warning"
        elif any(k in content for k in _BQ_META_KW):
            cls = "note-meta"
        else:
            cls = "note-info"
        return f'<blockquote class="{cls}">{content}</blockquote>'

    return re.sub(
        r"<blockquote>(.*?)</blockquote>", _classify, html, flags=re.DOTALL
    )


def wrap_title_banner(html):
    """Wrap first <h1> in a title-banner div."""
    return re.sub(
        r"<h1>(.*?)</h1>",
        r'<div class="title-banner"><h1>\1</h1></div>',
        html,
        count=1,
    )


def wrap_part_banners(html):
    """Wrap h1 elements containing 'Part' in a part-banner div."""
    return re.sub(
        r"<h1>(Part\s.*?)</h1>",
        r'<div class="part-banner"><h1>\1</h1></div>',
        html,
    )


def wrap_lockscreen_section(html):
    """Wrap lockscreen memo section in a page-break div."""
    return re.sub(
        r'<h1>([^<]*锁屏备忘[^<]*)</h1>(.*)',
        r'<div class="lockscreen-section"><h1 class="lockscreen-title">\1</h1>\2</div>',
        html,
        flags=re.DOTALL,
    )


def replace_hr_with_accent(html):
    """Replace <hr> with orange accent bars."""
    html = html.replace("<hr />", '<div class="accent-bar"></div>')
    html = html.replace("<hr>", '<div class="accent-bar"></div>')
    return html


def postprocess_html(html, *, full_report=False):
    """Apply all HTML post-processing in correct order.

    Args:
        html: Raw HTML body from markdown conversion.
        full_report: If True, also process Part banners and lockscreen sections
                     (for race-goal/race-review style reports).
    """
    html = classify_blockquotes(html)
    html = wrap_title_banner(html)
    if full_report:
        html = wrap_part_banners(html)
        html = wrap_lockscreen_section(html)
    html = replace_hr_with_accent(html)
    return html


def build_html_document(html_body, title="Marathon Copilot Report"):
    """Wrap processed HTML body in a full HTML document with CSS."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title>
<style>{CSS_DESIGN_SYSTEM}</style></head>
<body>{html_body}</body></html>"""


def md_to_pdf(md_text, pdf_path, *, title="Report", full_report=False):
    """Convert Markdown text to styled PDF using weasyprint + shared design system.

    Args:
        md_text: Markdown string.
        pdf_path: Output PDF path (str or Path).
        title: HTML title tag.
        full_report: Enable Part-banner and lockscreen processing.

    Returns:
        True on success, False if dependencies missing or generation fails.
    """
    try:
        import markdown as _md
        from weasyprint import HTML as _HTML
    except ImportError as exc:
        print(f"[WARN] PDF dependency missing ({exc}), skipping PDF generation.")
        return False

    html_body = _md.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])
    html_body = postprocess_html(html_body, full_report=full_report)
    full_html = build_html_document(html_body, title=title)

    try:
        _HTML(string=full_html).write_pdf(str(pdf_path))
        from pathlib import Path
        size_kb = Path(pdf_path).stat().st_size / 1024
        print(f"[OK] PDF generated: {pdf_path} ({size_kb:.0f} KB)")
        return True
    except Exception as exc:
        print(f"[WARN] PDF generation failed: {exc}")
        return False
