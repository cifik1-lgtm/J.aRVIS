"""
RAG Memory Engine for JARVIS — ChromaDB-powered long-term memory with semantic retrieval.

This module wraps the existing MemoryManager and adds:
- Persistent vector index via ChromaDB (no re-encoding on every search)
- Fast similarity search (milliseconds, not seconds)
- Auto-syncing between long_term.json and the vector DB
- Conversation ingestion for episodic memory
"""

import json
import os
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE_DIR / "memory" / "chroma_db"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Fix for Windows surrogate encoding in user profile paths
_SAFE_CACHE = "C:\\JarvisCache\\ai_models"
os.makedirs(_SAFE_CACHE, exist_ok=True)
os.environ["HF_HOME"] = _SAFE_CACHE
os.environ["TRANSFORMERS_CACHE"] = _SAFE_CACHE
os.environ["SENTENCE_TRANSFORMERS_HOME"] = _SAFE_CACHE
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class RAGMemoryEngine:
    """
    Vector-backed memory engine. Wraps ChromaDB for persistent, fast semantic search.
    Falls back to keyword search if chromadb/sentence-transformers are unavailable.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._client = None
        self._collection = None
        self._embedder = None
        self._ready = False

        # Boot in background so JARVIS starts instantly
        t = threading.Thread(target=self._initialize, daemon=True)
        t.start()

    def _initialize(self):
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer

            print("[RAG] 🧠 Initializing ChromaDB vector store...")
            self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            self._collection = self._client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"}
            )

            print("[RAG] 📐 Loading sentence embedding model...")
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")

            # Sync existing long_term.json into the vector DB
            self._sync_from_json()
            
            # Index Expert Skills from the /skills folder
            self.ingest_skills()

            self._ready = True
            print(f"[RAG] ✅ Ready — {self._collection.count()} vectors indexed.")

        except Exception as e:
            print(f"[RAG] ⚠️ Failed to initialize: {e}. Falling back to keyword search.")

    def _sync_from_json(self):
        """Load all memories from long_term.json into ChromaDB if not already indexed."""
        json_path = BASE_DIR / "memory" / "long_term.json"
        if not json_path.exists():
            return

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return

        docs, ids, metas = [], [], []
        for category, items in data.items():
            if not isinstance(items, dict):
                continue
            for key, entry in items.items():
                if not isinstance(entry, dict) or "value" not in entry:
                    continue
                doc_id = f"{category}::{key}"
                # Only add if not already in DB
                existing = self._collection.get(ids=[doc_id])
                if not existing["ids"]:
                    docs.append(entry["value"][:500])
                    ids.append(doc_id)
                    metas.append({
                        "category": category,
                        "key": key,
                        "updated": entry.get("updated", datetime.now().strftime("%Y-%m-%d"))
                    })

        if docs:
            embeddings = self._embedder.encode(docs, show_progress_bar=False).tolist()
            self._collection.add(documents=docs, ids=ids, metadatas=metas, embeddings=embeddings)
    def ingest_skills(self):
        """Index all .md files in the skills directory."""
        skills_dir = BASE_DIR / "skills"
        if not skills_dir.exists():
            return

        print("[RAG] 🧠 Ingesting Expert Skills from /skills...")
        for skill_file in skills_dir.rglob("*.md"):
            try:
                # Skip top-level README
                if skill_file.name.lower() == "readme.md" and skill_file.parent == skills_dir:
                    continue
                
                content = skill_file.read_text(encoding="utf-8")
                skill_name = skill_file.parent.name if skill_file.name.lower() == "skill.md" else skill_file.stem
                
                self.index_memory(
                    category="expert_skill",
                    key=skill_name,
                    value=content[:2000] # Index first 2k chars for retrieval
                )
            except Exception as e:
                print(f"[RAG] ⚠️ Skill indexing error ({skill_file.name}): {e}")

    def index_memory(self, category: str, key: str, value: str):
        """Add or update a single memory in the vector index."""
        if not self._ready:
            return
        try:
            doc_id = f"{category}::{key}"
            embedding = self._embedder.encode([value[:500]], show_progress_bar=False).tolist()
            meta = {
                "category": category,
                "key": key,
                "updated": datetime.now().strftime("%Y-%m-%d")
            }
            with self._lock:
                # Upsert (add or update)
                self._collection.upsert(
                    documents=[value[:500]],
                    ids=[doc_id],
                    metadatas=[meta],
                    embeddings=embedding
                )
        except Exception as e:
            print(f"[RAG] ⚠️ Index error: {e}")

    def index_conversation(self, user_text: str, jarvis_text: str):
        """Ingest a conversation turn as episodic memory."""
        if not self._ready or not user_text:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            doc_id = f"conversation::{ts}"
            combined = f"User: {user_text[:250]}\nJARVIS: {jarvis_text[:250]}"
            embedding = self._embedder.encode([combined], show_progress_bar=False).tolist()
            with self._lock:
                self._collection.add(
                    documents=[combined],
                    ids=[doc_id],
                    metadatas=[{"category": "conversation", "key": ts,
                                "updated": datetime.now().strftime("%Y-%m-%d")}],
                    embeddings=embedding
                )
        except Exception as e:
            print(f"[RAG] ⚠️ Conversation index error: {e}")

    def search(self, query: str, top_k: int = 5, category_filter: str = None) -> List[dict]:
        """
        Semantic search. Returns list of {category, key, value, score} dicts.
        Falls back to empty list if not ready.
        """
        if not self._ready:
            return []
        try:
            q_emb = self._embedder.encode([query], show_progress_bar=False).tolist()
            where = {"category": category_filter} if category_filter else None

            results = self._collection.query(
                query_embeddings=q_emb,
                n_results=min(top_k, max(self._collection.count(), 1)),
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            hits = []
            for i, doc in enumerate(results["documents"][0]):
                meta = results["metadatas"][0][i]
                dist = results["distances"][0][i]
                score = 1.0 - dist  # cosine distance → similarity
                if score > 0.25:
                    hits.append({
                        "category": meta.get("category", ""),
                        "key": meta.get("key", ""),
                        "value": doc,
                        "score": round(score, 3)
                    })
            return hits
        except Exception as e:
            print(f"[RAG] ⚠️ Search error: {e}")
            return []

    def format_rag_context(self, query: str, top_k: int = 4) -> str:
        """
        Returns a formatted string of the most relevant memories for injection
        into the JARVIS system prompt at call time.
        """
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""

        lines = ["[RAG MEMORY — Relevant context retrieved for this query]"]
        for h in hits:
            cat = h["category"].upper()
            lines.append(f"• [{cat}] {h['key'].replace('_', ' ').title()}: {h['value']}")
        lines.append("")
        return "\n".join(lines)

    def get_stats(self) -> dict:
        if not self._ready:
            return {"ready": False, "count": 0}
        return {"ready": True, "count": self._collection.count()}


# ============================================================================
# Singleton
# ============================================================================

_rag_engine: Optional[RAGMemoryEngine] = None


def get_rag_engine() -> RAGMemoryEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGMemoryEngine()
    return _rag_engine
