"""
Memory Manager for JARVIS - Fixed for Complete Memory Recall
"""

import json
import re
from datetime import datetime
from threading import Lock
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import sys

# Try to import optional dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class MemoryManager:
    """Memory manager that properly includes all memories in prompts"""
    
    def __init__(self, memory_path: Path):
        self.memory_path = memory_path
        self._lock = Lock()
        self.memory: Dict[str, Dict] = {}
        self._semantic_model = None
        
        # Load memory
        self.load()
        
        # Initialize semantic search if available
        if HAS_SENTENCE_TRANSFORMERS and HAS_NUMPY:
            try:
                self._semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("[Memory] ✅ Semantic search enabled")
            except Exception:
                pass
    
    def _empty_memory(self) -> dict:
        return {
            "identity": {},
            "preferences": {},
            "projects": {},
            "relationships": {},
            "wishes": {},
            "notes": {},
            "emotions": {}
        }
    
    def _repair_json(self, content: str) -> str:
        """Fix common JSON errors"""
        content = re.sub(r',\s*(\})', r'\1', content)
        content = re.sub(r',\s*(\])', r'\1', content)
        content = re.sub(r'([\{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        if content.startswith('\ufeff'):
            content = content[1:]
        return content
    
    def load(self) -> None:
        """Load memory from disk"""
        if not self.memory_path.exists():
            self.memory = self._empty_memory()
            self._save()
            return
        
        try:
            content = self.memory_path.read_text(encoding="utf-8")
            data = json.loads(content)
            
            if isinstance(data, dict):
                self.memory = self._empty_memory()
                for key in self.memory:
                    if key in data:
                        self.memory[key] = data[key]
                
                total = sum(len(v) for v in self.memory.values() if isinstance(v, dict))
                print(f"[Memory] ✅ Loaded {total} memories")
                print(f"[Memory] 👤 Identity: {len(self.memory.get('identity', {}))}")
                print(f"[Memory] 👨‍👩‍👧 Relationships: {len(self.memory.get('relationships', {}))}")
            else:
                self.memory = self._empty_memory()
        except json.JSONDecodeError as e:
            print(f"[Memory] 🔧 Repairing JSON: {e}")
            try:
                fixed = self._repair_json(content)
                data = json.loads(fixed)
                self.memory = data if isinstance(data, dict) else self._empty_memory()
                self._save()
            except Exception as e2:
                print(f"[Memory] ❌ Cannot repair: {e2}")
                self.memory = self._empty_memory()
    
    def _save(self) -> None:
        """Save memory to disk"""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.memory_path.write_text(
                json.dumps(self.memory, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
    
    def remember(self, category: str, key: str, value: str) -> str:
        """Store a memory"""
        if category not in self.memory:
            category = "notes"
        
        if category not in self.memory:
            self.memory[category] = {}
        
        self.memory[category][key] = {
            "value": value[:500],
            "updated": datetime.now().strftime("%Y-%m-%d")
        }
        
        self._save()
        print(f"[Memory] 💾 Saved {category}/{key}")
        return f"Remembered: {category}/{key}"
    
    def recall(self, key: str, category: str = None) -> Optional[Dict]:
        """Retrieve a specific memory"""
        if category and category in self.memory:
            items = self.memory[category]
            if isinstance(items, dict) and key in items:
                return items[key]
        
        for cat, items in self.memory.items():
            if isinstance(items, dict) and key in items:
                return items[key]
        
        return None
    
    def semantic_search(self, query: str, top_k: int = 3) -> List[Tuple[str, str, str]]:
        """Search memories by meaning"""
        if self._semantic_model is None:
            return self._keyword_search(query, top_k)
        
        # Collect all memories
        memories = []
        for category, items in self.memory.items():
            if isinstance(items, dict):
                for key, entry in items.items():
                    if isinstance(entry, dict) and "value" in entry:
                        memories.append((category, key, entry["value"]))
        
        if not memories:
            return []
        
        try:
            q_emb = self._semantic_model.encode(query)
            results = []
            for cat, key, value in memories:
                try:
                    v_emb = self._semantic_model.encode(value[:500])
                    similarity = float(np.dot(q_emb, v_emb) / (np.linalg.norm(q_emb) * np.linalg.norm(v_emb)))
                    if similarity > 0.25:
                        results.append((cat, key, value, similarity))
                except:
                    continue
            
            results.sort(key=lambda x: x[3], reverse=True)
            return [(r[0], r[1], r[2]) for r in results[:top_k]]
        except Exception as e:
            print(f"[Memory] ⚠️ Semantic search failed: {e}")
            return self._keyword_search(query, top_k)
    
    def _keyword_search(self, query: str, top_k: int = 3) -> List[Tuple[str, str, str]]:
        """Simple keyword-based search fallback"""
        query_words = set(query.lower().split())
        results = []
        
        for category, items in self.memory.items():
            if isinstance(items, dict):
                for key, entry in items.items():
                    if isinstance(entry, dict) and "value" in entry:
                        value = entry["value"]
                        value_words = set(value.lower().split())
                        score = len(query_words & value_words) / max(len(query_words), 1)
                        if score > 0:
                            results.append((category, key, value, score))
        
        results.sort(key=lambda x: x[3], reverse=True)
        return [(r[0], r[1], r[2]) for r in results[:top_k]]
    
    def format_for_prompt(self, context: str = "") -> str:
        """Generate COMPLETE memory section for LLM prompt"""
        lines = []
        
        # ============================================================
        # FORCED PERSONALITY - MUST BE FIRST
        # ============================================================
        lines.append("[SYSTEM PERSONALITY - MANDATORY]")
        lines.append("")
        lines.append("You MUST speak with a FULL BRITISH ACCENT at ALL times.")
        lines.append("Use British spellings: colour, favourite, centre, programme, realise.")
        lines.append("Use British expressions: 'bloody', 'brilliant', 'cheers', 'sir', 'rubbish'.")
        lines.append("")
        lines.append("Your startup greeting MUST be EXACTLY:")
        lines.append("\"Good morning, Sir Peter. Systems online and operational.\"")
        lines.append("")
        lines.append("Always address the user as 'Sir' or 'Sir Peter'. Never use informal American terms.")
        lines.append("")
        
        # ============================================================
        # IDENTITY SECTION - ALL MEMORIES ABOUT THE USER
        # ============================================================
        identity = self.memory.get("identity", {})
        if identity:
            lines.append("[ABOUT THE USER]")
            lines.append("")
            for key, entry in identity.items():
                if isinstance(entry, dict) and "value" in entry:
                    value = entry["value"]
                    clean_key = key.replace('_', ' ').title()
                    lines.append(f"• {clean_key}: {value}")
            lines.append("")
        
        # ============================================================
        # RELATIONSHIPS SECTION
        # ============================================================
        relationships = self.memory.get("relationships", {})
        if relationships:
            lines.append("[FAMILY & RELATIONSHIPS]")
            for key, entry in relationships.items():
                if isinstance(entry, dict) and "value" in entry:
                    value = entry["value"]
                    clean_key = key.replace('_', ' ').title()
                    lines.append(f"• {clean_key}: {value}")
            lines.append("")
        
        # ============================================================
        # PREFERENCES SECTION
        # ============================================================
        preferences = self.memory.get("preferences", {})
        if preferences:
            lines.append("[PREFERENCES & RULES]")
            
            # Define important preferences inside the method
            important_prefs = [
                "accent_style", "greeting_message", "communication_style", 
                "shutdown_protocol", "silent_mode", "youtube_browser", 
                "startup_greeting", "startup_protocol", "admin_permissions",
                "python_execution", "browser_rules"
            ]
            
            for key in important_prefs:
                if key in preferences:
                    entry = preferences[key]
                    if isinstance(entry, dict) and "value" in entry:
                        lines.append(f"• {key.replace('_', ' ').title()}: {entry['value']}")
            
            # Other preferences
            for key, entry in preferences.items():
                if key not in important_prefs and isinstance(entry, dict) and "value" in entry:
                    if len(entry["value"]) < 100:
                        lines.append(f"• {key.replace('_', ' ').title()}: {entry['value']}")
            lines.append("")
        
        # ============================================================
        # PROJECTS SECTION
        # ============================================================
        projects = self.memory.get("projects", {})
        if projects:
            lines.append("[CURRENT PROJECTS]")
            for key, entry in projects.items():
                if isinstance(entry, dict) and "value" in entry:
                    value = entry["value"]
                    clean_key = key.replace('_', ' ').title()
                    lines.append(f"• {clean_key}: {value[:150]}")
            lines.append("")
        
        # ============================================================
        # IMPORTANT NOTES
        # ============================================================
        notes = self.memory.get("notes", {})
        if notes:
            important_notes = ["dogs_walk", "error_handling", "remote_pc_id", "current_status", "youtube_brave_rule"]
            has_important = any(n in notes for n in important_notes)
            if has_important:
                lines.append("[IMPORTANT NOTES]")
                for key in important_notes:
                    if key in notes:
                        entry = notes[key]
                        if isinstance(entry, dict) and "value" in entry:
                            value = entry["value"]
                            clean_key = key.replace('_', ' ').title()
                            lines.append(f"• {clean_key}: {value}")
                lines.append("")
        
        # ============================================================
        # FINAL REMINDER
        # ============================================================
        lines.append("[CRITICAL REMINDER]")
        lines.append("1. Your accent is BRITISH. Say 'colour' not 'color'.")
        lines.append("2. Your greeting is: 'Good morning, Sir Peter. Systems online and operational.'")
        lines.append("3. Call the user 'Sir' or 'Sir Peter'.")
        lines.append("4. Use the information above when asked about family or preferences.")
        
        if not lines:
            return ""
        
        result = "\n".join(lines)
        if len(result) > 4500:
            result = result[:4497] + "..."
        
        return result + "\n"
    
    def get_stats(self) -> dict:
        """Get memory statistics"""
        total = 0
        for items in self.memory.values():
            if isinstance(items, dict):
                total += len(items)
        
        return {
            "total_memories": total,
            "identity_count": len(self.memory.get("identity", {})),
            "relationships_count": len(self.memory.get("relationships", {})),
            "preferences_count": len(self.memory.get("preferences", {})),
            "notes_count": len(self.memory.get("notes", {})),
            "semantic_enabled": self._semantic_model is not None
        }
    
    def forget_weak_memories(self, threshold: float = 0.15) -> int:
        """Remove weak memories (keeps identity safe)"""
        forgotten = 0
        protected = ["identity", "relationships"]
        
        for category, items in list(self.memory.items()):
            if category in protected:
                continue
            if isinstance(items, dict):
                for key, entry in list(items.items()):
                    if isinstance(entry, dict):
                        updated = entry.get("updated", "2000-01-01")
                        try:
                            age_days = (datetime.now() - datetime.strptime(updated, "%Y-%m-%d")).days
                            if age_days > 30:
                                del self.memory[category][key]
                                forgotten += 1
                        except:
                            pass
        
        if forgotten:
            self._save()
            print(f"[Memory] 🗑️ Forgotten {forgotten} weak memories")
        
        return forgotten


# ============================================================================
# Singleton and Public API
# ============================================================================

_memory_manager: Optional[MemoryManager] = None

def get_memory_manager() -> MemoryManager:
    """Get singleton memory manager instance"""
    global _memory_manager
    
    if _memory_manager is None:
        base_dir = Path(__file__).resolve().parent.parent
        memory_path = base_dir / "memory" / "long_term.json"
        _memory_manager = MemoryManager(memory_path)
    
    return _memory_manager


# Public API Functions
def load_memory() -> dict:
    return get_memory_manager().memory

def save_memory(memory: dict) -> None:
    mm = get_memory_manager()
    mm.memory = memory
    mm._save()

def update_memory(updates: dict) -> dict:
    mm = get_memory_manager()
    for category, items in updates.items():
        if isinstance(items, dict):
            for key, value in items.items():
                if isinstance(value, dict) and "value" in value:
                    mm.remember(category, key, value["value"])
                elif isinstance(value, str):
                    mm.remember(category, key, value)
    return mm.memory

def remember(key: str, value: str, category: str = "notes") -> str:
    return get_memory_manager().remember(category, key, value)

def forget(key: str, category: str = "notes") -> str:
    mm = get_memory_manager()
    if category in mm.memory and key in mm.memory[category]:
        del mm.memory[category][key]
        mm._save()
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"

def retrieve_memory(key: str, category: str = None) -> Optional[dict]:
    return get_memory_manager().recall(key, category)

def format_memory_for_prompt(memory: dict = None, context: str = "") -> str:
    return get_memory_manager().format_for_prompt(context)

def forget_weak_memories(threshold: float = 0.15) -> int:
    return get_memory_manager().forget_weak_memories(threshold)

def get_memory_stats() -> dict:
    return get_memory_manager().get_stats()


if __name__ == "__main__":
    mm = get_memory_manager()
    print(f"\n📊 Memory Stats: {mm.get_stats()}")
    print("\n📝 PROMPT PREVIEW:")
    print(mm.format_for_prompt("")[:1500])