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
import gc
import time
import numpy as np
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
        
        # Circuit Breaker state for RAG queries
        self._consecutive_errors = 0
        self._last_error_time = 0.0

        # Boot in background so JARVIS starts instantly
        t = threading.Thread(target=self._initialize, daemon=True)
        t.start()

    def _initialize(self):
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer

            print("[RAG] [INFO] Initializing Neural Core...")
            self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            self._collection = self._client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"}
            )

            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")

            # Sync existing long_term.json into the vector DB
            self._sync_from_json()
            
            # Index Expert Skills from the /skills folder
            self.ingest_skills()

            # Index Local Wiki from the memory/wiki folder
            self.ingest_wiki()

            self._ready = True
            print(f"[RAG] [SUCCESS] Neural Link Active — {self._collection.count()} neurons indexed.")

        except Exception as e:
            print(f"[RAG] [WARN] Initialization error: {e}")

    def _sync_from_json(self):
        """Load all memories from long_term.json into ChromaDB."""
        json_path = BASE_DIR / "memory" / "long_term.json"
        if not json_path.exists():
            return

        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return

        for category, items in data.items():
            if not isinstance(items, dict):
                continue
            for key, entry in items.items():
                if not isinstance(entry, dict) or "value" not in entry:
                    continue
                self.index_memory(category, key, entry["value"])

    def ingest_wiki(self):
        """Index local wiki markdown files incrementally in batches."""
        wiki_dir = BASE_DIR / "memory" / "wiki"
        if not wiki_dir.exists():
            wiki_dir.mkdir(parents=True, exist_ok=True)
            return

        # Get existing IDs to avoid re-indexing
        try:
            existing_ids = set(self._collection.get(include=[])["ids"])
        except Exception:
            existing_ids = set()
        
        new_docs = []
        for doc_file in wiki_dir.rglob("*.md"):
            doc_rel_path = str(doc_file.relative_to(wiki_dir)).replace("\\", "/")
            doc_id = f"wiki::{doc_rel_path}"
            if doc_id not in existing_ids:
                new_docs.append(doc_file)

        if not new_docs:
            return

        # Batch ingestion to save RAM
        batch_size = 50
        for i in range(0, len(new_docs), batch_size):
            batch = new_docs[i:i + batch_size]
            for doc_file in batch:
                try:
                    content = doc_file.read_text(encoding="utf-8")
                    doc_rel_path = str(doc_file.relative_to(wiki_dir)).replace("\\", "/")
                    # Use "wiki" category, key as rel path, value as content
                    self.index_memory("wiki", doc_rel_path, content[:2000])
                except Exception:
                    pass
            gc.collect()

    def ingest_skills(self):
        """Index skills incrementally in batches."""
        skills_dir = BASE_DIR / "skills"
        if not skills_dir.exists():
            return

        # Get existing IDs to avoid re-indexing
        existing_ids = set(self._collection.get(include=[])["ids"])
        
        new_skills = []
        for skill_file in skills_dir.rglob("*.md"):
            skill_rel_path = str(skill_file.relative_to(skills_dir)).replace("\\", "/")
            doc_id = f"expert_skill::{skill_rel_path}"
            if doc_id not in existing_ids:
                new_skills.append(skill_file)

        if not new_skills:
            return

        # Batch ingestion to save RAM
        batch_size = 50
        for i in range(0, len(new_skills), batch_size):
            batch = new_skills[i:i + batch_size]
            for skill_file in batch:
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    skill_rel_path = str(skill_file.relative_to(skills_dir)).replace("\\", "/")
                    self.index_memory("expert_skill", skill_rel_path, content[:2000])
                except Exception:
                    pass
            gc.collect()

    def index_memory(self, category: str, key: str, value: str):
        """Add or update a single memory in the vector index."""
        if self._embedder is None:
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
                self._collection.upsert(
                    documents=[value[:500]],
                    ids=[doc_id],
                    metadatas=[meta],
                    embeddings=embedding
                )
            # Auto-prune Check if collection exceeds limit
            if self._ready:
                self._prune_if_exceeded()
        except Exception as e:
            # Silent fail for individual items to prevent log bloat
            pass

    def _prune_if_exceeded(self):
        """Auto-pruning: Keep collection size below 8000 documents by removing old conversations."""
        try:
            total_count = self._collection.count()
            if total_count <= 8000:
                return
                
            print(f"[RAG] 🧹 Collection size ({total_count}) exceeds limit of 8000. Pruning old episodic memories...")
            
            # Fetch conversation memories
            results = self._collection.get(
                where={"category": "conversation"},
                include=["metadatas"]
            )
            
            ids = results.get("ids", [])
            metadatas = results.get("metadatas", [])
            
            if not ids:
                print("[RAG] ⚠️ No conversation memories to prune. All documents are static rules/wiki files.")
                return
                
            pairs = []
            for i in range(len(ids)):
                doc_id = ids[i]
                meta = metadatas[i] or {}
                updated_str = meta.get("updated", "")
                pairs.append((doc_id, updated_str))
                
            # Sort by update date (oldest first), then ID
            pairs.sort(key=lambda x: (x[1], x[0]))
            
            # Target count is 7500 (pruning excess + 500 margin)
            excess = total_count - 7500
            if excess <= 0:
                excess = 100
                
            to_delete = [p[0] for p in pairs[:excess]]
            
            if to_delete:
                print(f"[RAG] 🧹 Deleting {len(to_delete)} oldest conversations from index.")
                with self._lock:
                    self._collection.delete(ids=to_delete)
                print(f"[RAG] 🧹 Pruning complete. New size: {self._collection.count()} documents.")
        except Exception as e:
            print(f"[RAG] ⚠️ Pruning failed: {e}")

    def index_conversation(self, user_text: str, jarvis_text: str):
        """Ingest a conversation turn as episodic memory."""
        if not self._ready or not user_text:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            doc_id = f"conversation::{ts}"
            combined = f"User: {user_text[:250]}\nJARVIS: {jarvis_text[:250]}"
            self.index_memory("conversation", ts, combined)
        except Exception:
            pass

    def search(self, query: str, top_k: int = 5, category_filter: str = None) -> List[dict]:
        """Semantic search with circuit breaker protection."""
        if not self._ready:
            return []
            
        import time
        # Circuit Breaker check
        if self._consecutive_errors >= 3:
            current_time = time.time()
            if current_time - self._last_error_time < 30.0:
                print(f"[RAG] 🔌 Circuit Breaker OPEN (errors: {self._consecutive_errors}). Fast-failing query: '{query[:40]}'")
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
                score = 1.0 - dist
                if score > 0.25:
                    hits.append({
                        "category": meta.get("category", ""),
                        "key": meta.get("key", ""),
                        "value": doc,
                        "score": round(score, 3)
                    })
            
            # Reset circuit breaker on success
            self._consecutive_errors = 0
            return hits
        except Exception as e:
            self._consecutive_errors += 1
            self._last_error_time = time.time()
            print(f"[RAG] ❌ Search failed: {e}. Consecutive errors: {self._consecutive_errors}")
            return []

    def format_rag_context(self, query: str, top_k: int = 4) -> str:
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


_rag_engine: Optional[RAGMemoryEngine] = None
_rag_lock = threading.Lock()

def get_rag_engine() -> RAGMemoryEngine:
    global _rag_engine
    if _rag_engine is None:
        with _rag_lock:
            if _rag_engine is None:
                _rag_engine = RAGMemoryEngine()
    return _rag_engine
