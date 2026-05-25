import chromadb
import os
import json
from datetime import datetime
import uuid
import sys

# Define the base path based on JARVIS structure
BASE_DIR = "C:\\Users\\eva\\Desktop\\JARVIS_SHARE\\CifikAI"
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
MEMORY_DB_PATH = os.path.join(MEMORY_DIR, "chroma_db")
COLLECTION_NAME = "jarvis_persistent_memories_evolved"

class PersistentMemorySystem:
    def __init__(self):
        """Initializes the ChromaDB client and collection with hierarchical structure."""
        self.client = None
        self.collection = None
        try:
            if not os.path.exists(MEMORY_DIR):
                os.makedirs(MEMORY_DIR)
            
            self.client = chromadb.PersistentClient(path=MEMORY_DB_PATH)
            # Use a new collection name for the evolved system
            self.collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"Evolved PersistentMemorySystem initialized. DB Path: {MEMORY_DB_PATH}")
        except Exception as e:
            print(f"Error initializing Evolved PersistentMemorySystem: {e}")
            raise RuntimeError(f"Critical Memory System failure: {e}")

    def _generate_id(self):
        """Generates a unique UUID."""
        return str(uuid.uuid4())

    def save(self, text: str, category: str = "mid_term", importance: int = 3, metadata: dict = None):
        """
        Saves memory with hierarchical categorization and metadata filtering.
        Categories: short_term (ephemeral), mid_term (contextual), long_term (facts, reflection), preference.
        """
        if not self.collection:
            return "Memory system not initialized."

        memory_id = self._generate_id()
        meta = {
            "category": category,
            "importance": importance,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            meta.update(metadata)

        try:
            self.collection.add(
                documents=[text],
                ids=[memory_id],
                metadatas=[meta]
            )
            return f"Memory saved ({category}): {memory_id}"
        except Exception as e:
            return f"Failed to save memory: {e}"

    def run(self, query: str, category: str = None, limit: int = 5):
        """
        Unified run function for semantic search, compatible with JARVIS tools.
        Implements metadata filtering based on category for hierarchical retrieval.
        """
        if not self.collection:
            return "Memory system not initialized."
        
        filter_criteria = {}
        if category:
            filter_criteria["category"] = category

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=filter_criteria if category else None
            )
            
            relevant_memories = []
            if results.get('documents') and results['documents'][0]:
                for doc, meta, distance in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
                    relevant_memories.append({
                        "text": doc,
                        "metadata": meta,
                        "relevance_score": 1 - distance
                    })
            return relevant_memories
        except Exception as e:
            print(f"Error retrieving memory: {e}")
            return []

    def run_test(self):
        """Tests the evolved memory system."""
        print("Running Evolved Persistent Memory System self-test...")
        
        # Test Save
        self.save("Sir Peter prefers a British accent.", category="preference", importance=5)
        self.save("Evolved Persistent Memory System implemented.", category="reflection", importance=4)
        self.save("Current session context data.", category="short_term", importance=1)

        # Test Run (Semantic Retrieval)
        query = "What is Sir Peter's preference?"
        results = self.run(query, limit=1)
        print(f"Test Retrieval Results for '{query}': {results}")

        query_filtered = "System status"
        results_filtered = self.run(query_filtered, category="reflection", limit=1)
        print(f"Test Filtered Retrieval Results for '{query_filtered}' (Category: reflection): {results_filtered}")

        if results and results_filtered:
            return "Persistent Memory System Evolution: Success."
        else:
            return "Persistent Memory System Evolution: Failed."

if __name__ == "__main__":
    try:
        mem_sys = PersistentMemorySystem()
        print(mem_sys.run_test())
    except Exception as e:
        print(f"Evolution Test Failed: {e}")
