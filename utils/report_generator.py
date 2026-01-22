
import os
import markdown
from datetime import datetime

# --- CONFIGURATION ---
CSS_STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600&display=swap');

    :root {
        --bg-color: #0F172A;
        --card-bg: #1E293B;
        --text-primary: #E2E8F0;
        --text-secondary: #94A3B8;
        --accent-color: #0EA5E9; /* Sky Blue */
        --accent-glow: rgba(14, 165, 233, 0.2);
        --danger-color: #EF4444;
        --border-color: #334155;
    }

    body {
        font-family: 'Inter', sans-serif;
        background-color: var(--bg-color);
        color: var(--text-primary);
        line-height: 1.6;
        margin: 0;
        padding: 40px;
        max-width: 900px;
        margin-left: auto;
        margin-right: auto;
    }

    /* TYPOGRAPHY */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'JetBrains Mono', monospace;
        color: #fff;
        margin-top: 2em;
        margin-bottom: 0.8em;
    }

    h1 {
        font-size: 2.5rem;
        border-bottom: 2px solid var(--accent-color);
        padding-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: -1px;
    }

    h2 {
        font-size: 1.8rem;
        color: var(--accent-color);
    }

    p {
        margin-bottom: 1.2em;
        color: var(--text-secondary);
    }

    strong {
        color: #fff;
        font-weight: 600;
    }

    /* COMPONENTS */
    blockquote {
        border-left: 4px solid var(--accent-color);
        background: var(--card-bg);
        margin: 1.5em 0;
        padding: 1em 1.5em;
        border-radius: 0 8px 8px 0;
        font-style: italic;
    }

    code {
        font-family: 'JetBrains Mono', monospace;
        background: #000;
        padding: 0.2em 0.4em;
        border-radius: 4px;
        font-size: 0.9em;
        color: #10B981; /* Green */
    }

    pre {
        background: #000;
        padding: 1.5em;
        border-radius: 8px;
        overflow-x: auto;
        border: 1px solid var(--border-color);
    }

    pre code {
        background: transparent;
        padding: 0;
        color: #E2E8F0;
    }

    hr {
        border: 0;
        height: 1px;
        background: var(--border-color);
        margin: 3em 0;
    }

    /* TABLES */
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 2em 0;
        background: var(--card-bg);
        border-radius: 8px;
        overflow: hidden;
    }

    th, td {
        padding: 12px 15px;
        text-align: left;
        border-bottom: 1px solid var(--border-color);
    }

    th {
        background: rgba(0,0,0,0.3);
        font-family: 'JetBrains Mono', monospace;
        color: var(--accent-color);
        text-transform: uppercase;
        font-size: 0.85em;
    }

    /* HEADER / FOOTER */
    .report-header {
        text-align: center;
        margin-bottom: 60px;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 40px;
    }

    .report-meta {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .confidential-mark {
        color: var(--danger-color);
        border: 1px solid var(--danger-color);
        padding: 4px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 10px;
        font-weight: bold;
    }

    .toc {
        background: var(--card-bg);
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 40px;
        border: 1px solid var(--border-color);
    }
    
    .toc h3 {
        margin-top: 0;
        font-size: 1.2rem;
    }
    
    .toc ul {
        list-style: none;
        padding-left: 0;
    }
    
    .toc li {
        margin-bottom: 8px;
    }
    
    .toc a {
        color: var(--text-secondary);
        text-decoration: none;
        transition: color 0.2s;
    }
    
    .toc a:hover {
        color: var(--accent-color);
    }

    @media print {
        body {
            background-color: #fff;
            color: #000;
        }
        .report-header {
            page-break-after: avoid;
        }
        pre, blockquote {
            page-break-inside: avoid;
        }
    }
</style>
"""

def generate_report(content_markdown: str, output_filename: str, title: str = "Warroom Intelligence Report"):
    """
    Converts Markdown content into a styled HTML report.
    """
    
    # 1. Convert Markdown to HTML
    # Extensions: extra (tables, etc.), toc (Table of Contents), codehilite
    html_body = markdown.markdown(
        content_markdown, 
        extensions=['extra', 'toc', 'codehilite', 'sane_lists']
    )
    
    # 2. Build the Document Structure
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    full_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        {CSS_STYLE}
    </head>
    <body>
        <div class="report-header">
            <div class="confidential-mark">CONFIDENTIAL // EYES ONLY</div>
            <h1>{title}</h1>
            <div class="report-meta">
                GENERATED BY: PROJECT OMNISCIENCE v6.0<br>
                DATE: {timestamp}<br>
                SECURITY CLEARANCE: LEVEL 5
            </div>
        </div>

        <div class="content">
            {html_body}
        </div>
        
        <script>
            // Simple script to open print dialog automatically (optional)
            // window.print();
        </script>
    </body>
    </html>
    """
    
    # 3. Write to File
    # Ensure directory exists
    if os.path.dirname(output_filename):
        os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(full_html)
        
    return os.path.abspath(output_filename)

if __name__ == "__main__":
    # Test Run
    sample_md = """
    # Executive Summary
    This is a test of the **Warroom Report Generator**.
    
    ## Key Findings
    1. The market is **volatile**.
    2. AI adoption is *accelerating*.
    
    ### Financial Projections
    | Year | Revenue |
    |------|---------|
    | 2025 | $10M    |
    | 2026 | $50M    |
    
    ```python
    def optimize_revenue():
        return "Profit"
    ```
    """
    out = generate_report(sample_md, "test_report.html")
    print(f"Report generated: {out}")
