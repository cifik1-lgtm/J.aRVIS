import json
import numpy as np
from pathlib import Path
from google import genai
import sys

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
DB_PATH = BASE_DIR / "memory" / "vector_db.json"
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

def _get_api_key():
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)["gemini_api_key"]
    except Exception:
        return ""

client = None
def get_client():
    global client
    if client is None:
        client = genai.Client(api_key=_get_api_key())
    return client

def get_embedding(text: str) -> list[float]:
    c = get_client()
    response = c.models.embed_content(
        model="text-embedding-004",
        contents=text
    )
    return response.embeddings[0].values

def load_db():
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"docs": [], "embeddings": []}

def save_db(db):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f)

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0: return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def semantic_search(parameters: dict, player=None) -> str:
    action = parameters.get("action", "search")
    
    if action == "index_file":
        path = parameters.get("path", "")
        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            return f"File not found: {path}"
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            return "Could not read file. Must be text."
        
        chunks = [content[i:i+1000] for i in range(0, len(content), 1000)]
        db = load_db()
        for i, chunk in enumerate(chunks):
            emb = get_embedding(chunk)
            db["docs"].append({"path": str(p), "chunk": chunk, "index": i})
            db["embeddings"].append(emb)
        save_db(db)
        return f"Indexed {len(chunks)} chunks from {p.name}"

    elif action == "search":
        query = parameters.get("query", "")
        if not query: return "No query provided."
        
        db = load_db()
        if not db["docs"]: return "Deep Memory is empty. Index some files first using index_file action."
        
        query_emb = get_embedding(query)
        
        results = []
        for doc, emb in zip(db["docs"], db["embeddings"]):
            sim = cosine_similarity(query_emb, emb)
            results.append((sim, doc))
        
        results.sort(key=lambda x: x[0], reverse=True)
        top = results[:3]
        
        res_str = f"Top Deep Memory results for '{query}':\n\n"
        for sim, doc in top:
            if sim > 0.4:
                res_str += f"Score: {sim:.2f} | File: {doc['path']}\nContent:\n{doc['chunk']}\n\n"
        
        if res_str.strip() == f"Top Deep Memory results for '{query}':":
            return "No highly relevant information found in Deep Memory."
        return res_str
        
    return "Unknown action."
