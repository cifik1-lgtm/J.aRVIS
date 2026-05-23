import os
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import re

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

BASE_DIR = Path(__file__).resolve().parent.parent
WIKI_DIR = BASE_DIR / "memory" / "wiki"
WIKI_DIR.mkdir(parents=True, exist_ok=True)

def deep_research(parameters: dict, player=None) -> str:
    """
    Advanced Deep Research Mode.
    Downloads web content or parses PDFs and stores them as markdown in the RAG Wiki.
    """
    url = parameters.get("url")
    file_path = parameters.get("file_path")
    
    content = ""
    title = "research_doc"

    try:
        if url:
            # Web scraping
            title = re.sub(r'[^a-zA-Z0-9]', '_', url)[:50]
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract meaningful text
            for script in soup(["script", "style", "nav", "footer"]):
                script.extract()
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            content = '\n'.join(chunk for chunk in chunks if chunk)
            title = soup.title.string if soup.title else title
            title = re.sub(r'[^a-zA-Z0-9]', '_', title)[:50]

        elif file_path:
            # File parsing
            file_p = Path(file_path)
            if not file_p.exists():
                return f"Error: File not found {file_path}"
                
            title = file_p.stem
            if file_p.suffix.lower() == '.pdf':
                if not PyPDF2:
                    return "Error: PyPDF2 is not installed. Run 'pip install PyPDF2'."
                with open(file_p, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            content += page_text + "\n"
            else:
                # Assume text file
                with open(file_p, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
        else:
            return "Error: Please provide a 'url' or 'file_path' to research."

        if not content.strip():
            return "Error: No text could be extracted."

        # Save to Wiki
        safe_title = re.sub(r'[^a-zA-Z0-9_]', '', title.replace(' ', '_'))
        out_path = WIKI_DIR / f"{safe_title}.md"
        
        # Add basic markdown header
        md_content = f"# {title}\n\n"
        if url:
            md_content += f"**Source URL:** {url}\n\n"
        md_content += content
        
        out_path.write_text(md_content, encoding="utf-8")
        
        # Trigger RAG Engine Update
        try:
            from memory.rag_engine import get_rag_engine
            engine = get_rag_engine()
            engine.ingest_wiki()
        except Exception as e:
            if player:
                player.write_log(f"⚠️ Could not trigger auto-ingest: {e}")

        return f"Research complete. Extracted {len(content)} characters and saved to RAG Wiki as '{safe_title}.md'. JARVIS can now search this."

    except Exception as e:
        return f"Research Failed: {str(e)}"
