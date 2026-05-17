import json
import os
import sys

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.tools import TOOL_DECLARATIONS

html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JARVIS Core Capabilities</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Fira+Code:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(20, 25, 40, 0.6);
            --card-border: rgba(60, 130, 250, 0.2);
            --text-main: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --accent-glow: rgba(59, 130, 246, 0.5);
            --code-bg: rgba(10, 15, 25, 0.8);
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: 'Outfit', sans-serif;
            margin: 0;
            padding: 0;
            line-height: 1.6;
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.08) 0%, transparent 50%);
            background-attachment: fixed;
        }

        header {
            text-align: center;
            padding: 4rem 2rem 2rem;
            position: relative;
        }

        h1 {
            font-size: 3.5rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        .subtitle {
            font-size: 1.2rem;
            color: var(--text-muted);
            margin-top: 1rem;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 2rem;
        }

        .tool-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 2rem;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
        }

        .tool-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: linear-gradient(to bottom, #3b82f6, #8b5cf6);
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .tool-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3), 0 0 20px var(--accent-glow);
            border-color: rgba(60, 130, 250, 0.4);
        }

        .tool-card:hover::before {
            opacity: 1;
        }

        .tool-name {
            font-size: 1.5rem;
            font-weight: 600;
            color: #fff;
            margin: 0 0 1rem 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .tool-name::after {
            content: '';
            flex-grow: 1;
            height: 1px;
            background: linear-gradient(90deg, var(--card-border), transparent);
        }

        .tool-desc {
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-bottom: 1.5rem;
            flex-grow: 1;
        }

        .params-title {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #cbd5e1;
            margin-bottom: 0.5rem;
            font-weight: 600;
        }

        .code-block {
            background: var(--code-bg);
            border-radius: 8px;
            padding: 1rem;
            font-family: 'Fira Code', monospace;
            font-size: 0.85rem;
            color: #6ee7b7;
            overflow-x: auto;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .required-badge {
            display: inline-block;
            background: rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: bold;
            margin-left: 5px;
            vertical-align: middle;
        }

        .type-badge {
            color: #93c5fd;
            font-style: italic;
        }

        ul.param-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        ul.param-list li {
            margin-bottom: 0.4rem;
            line-height: 1.4;
        }

        .param-key {
            color: #fb7185;
            font-weight: 600;
        }

        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-color);
        }
        ::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #475569;
        }
    </style>
</head>
<body>

    <header>
        <h1>JARVIS Neural Matrix</h1>
        <div class="subtitle">Complete Diagnostic & Tool Capability Index</div>
    </header>

    <div class="container">
        {cards_html}
    </div>

    <script>
        // Subtle entrance animation
        document.querySelectorAll('.tool-card').forEach((card, index) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            setTimeout(() => {
                card.style.transition = 'all 0.6s cubic-bezier(0.25, 0.8, 0.25, 1)';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, index * 50);
        });
    </script>
</body>
</html>
"""

cards_html = ""
for tool in TOOL_DECLARATIONS:
    name = tool.get('name', 'Unknown')
    desc = tool.get('description', 'No description available.')
    params = tool.get('parameters', {}).get('properties', {})
    required = tool.get('parameters', {}).get('required', [])

    param_html = ""
    if params:
        param_html += '<ul class="param-list">'
        for k, v in params.items():
            req_badge = '<span class="required-badge">REQ</span>' if k in required else ''
            ptype = v.get('type', 'STRING').lower()
            enum_vals = v.get('enum', [])
            
            pdesc = v.get('description', '')
            if enum_vals:
                pdesc += f" (Options: {', '.join(enum_vals)})"
                
            param_html += f'<li><span class="param-key">{k}</span> <span class="type-badge">[{ptype}]</span>{req_badge}: {pdesc}</li>'
        param_html += '</ul>'
    else:
        param_html = '<div style="color: #64748b; font-size: 0.85rem; font-style: italic;">No parameters required.</div>'

    card = f"""
        <div class="tool-card">
            <h2 class="tool-name">{name}</h2>
            <div class="tool-desc">{desc}</div>
            <div class="params-title">Parameters</div>
            <div class="code-block">
                {param_html}
            </div>
        </div>
    """
    cards_html += card

final_html = html_template.replace('{cards_html}', cards_html)

output_path = os.path.expanduser(r"~\Desktop\JARVIS_Tools.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write(final_html)

print(f"Generated successfully at {output_path}")
