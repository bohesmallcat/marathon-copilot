#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import markdown
from playwright.sync_api import sync_playwright
import os

def convert_md_to_pdf(md_file, pdf_file):
    """Convert markdown file to PDF with proper Chinese rendering"""
    
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML
    html = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
    
    # Create HTML document with proper styling for Chinese
    html_doc = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>马拉松 PB 胜算预测报告</title>
    <style>
        body {{
            font-family: "Microsoft YaHei", "微软雅黑", "SimHei", "黑体", "Arial", sans-serif;
            line-height: 1.6;
            margin: 30px;
            color: #333;
            font-size: 10pt;
            word-wrap: break-word;
            word-break: break-word;
        }}
        h1 {{
            font-size: 18pt;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            page-break-before: always;
        }}
        h1:first-of-type {{
            page-break-before: auto;
        }}
        h2 {{
            font-size: 14pt;
            color: #34495e;
            border-bottom: 1px solid #bdc3c7;
            padding-bottom: 5px;
            margin-top: 20px;
        }}
        h3 {{
            font-size: 12pt;
            color: #7f8c8d;
            margin-top: 15px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            font-size: 9pt;
            word-wrap: break-word;
            word-break: break-word;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            vertical-align: top;
            word-wrap: break-word;
            word-break: break-word;
            white-space: normal;
            max-width: 200px;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
            white-space: nowrap;
        }}
        td {{
            hyphens: auto;
        }}
        code {{
            background-color: #f8f9fa;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: "Consolas", "Monaco", monospace;
        }}
        pre {{
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #3498db;
            margin-left: 0;
            padding-left: 20px;
            color: #7f8c8d;
        }}
        strong {{
            color: #2c3e50;
        }}
        .page-break {{
            page-break-before: always;
        }}
        @media print {{
            body {{
                margin: 20px;
            }}
            .no-print {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    {html}
</body>
</html>
"""
    
    # Write HTML to temporary file
    temp_html = "temp_report.html"
    with open(temp_html, 'w', encoding='utf-8') as f:
        f.write(html_doc)
    
    # Convert HTML to PDF using Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Load the HTML file
        page.goto(f"file://{os.path.abspath(temp_html)}")
        
        # Wait for page to load
        page.wait_for_load_state("networkidle")
        
        # Generate PDF
        page.pdf(
            path=pdf_file,
            format="A4",
            print_background=True,
            margin={
                "top": "15mm",
                "right": "15mm",
                "bottom": "15mm",
                "left": "15mm"
            }
        )
        
        browser.close()
    
    # Clean up temporary HTML file
    os.remove(temp_html)
    
    print("PDF generated successfully!")

if __name__ == "__main__":
    # Convert report: python md_to_pdf.py or modify filenames below
    convert_md_to_pdf("example_report.md", "example_report.pdf")
