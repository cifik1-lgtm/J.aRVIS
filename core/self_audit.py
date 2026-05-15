"""
JARVIS Self-Audit System - Detects changes to configuration, tools, and brains
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

class SelfAudit:
    def __init__(self, config_path: Path, tools_declarations: List[Dict]):
        self.config_path = config_path
        self.tools_declarations = tools_declarations
        self.state_file = Path(__file__).parent.parent / "memory" / "self_audit_state.json"
        
    def compute_config_hash(self) -> str:
        """Create a hash of the current configuration"""
        if not self.config_path.exists():
            return ""
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        # Remove volatile keys that change often
        volatile_keys = ["last_audit", "session_id", "timestamp"]
        for key in volatile_keys:
            config.pop(key, None)
        
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    def compute_tools_hash(self) -> str:
        """Create a hash of the registered tools"""
        tools_names = sorted([t.get("name", "") for t in self.tools_declarations])
        tools_str = json.dumps(tools_names, sort_keys=True)
        return hashlib.sha256(tools_str.encode()).hexdigest()
    
    def compute_brains_hash(self) -> str:
        """Create a hash of available brains from brain_router"""
        try:
            # Simpler: read from the engines file if you save it
            engines_file = Path(__file__).parent.parent / "memory" / "engines_status.json"
            if engines_file.exists():
                with open(engines_file, 'r') as f:
                    engines = json.load(f)
                engines_str = json.dumps(engines, sort_keys=True)
                return hashlib.sha256(engines_str.encode()).hexdigest()
        except:
            pass
        return ""
    
    def load_previous_state(self) -> Dict:
        """Load the last known state"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_current_state(self, state: Dict):
        """Save current state for future comparison"""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def compute_source_file_hashes(self) -> Dict[str, str]:
        """Create a dictionary mapping each Python file to its hash"""
        file_hashes = {}
        try:
            base_dir = Path(__file__).parent.parent
            py_files = sorted(base_dir.rglob("*.py"))
            
            # Exclude virtual envs or huge cached dirs just in case
            py_files = [f for f in py_files if ".venv" not in f.parts and "__pycache__" not in f.parts]
            
            for pf in py_files:
                try:
                    # Get relative path for cleaner output (e.g. 'ui.py' or 'actions/bug_hunter.py')
                    rel_path = str(pf.relative_to(base_dir)).replace('\\', '/')
                    with open(pf, 'rb') as f:
                        file_hashes[rel_path] = hashlib.sha256(f.read()).hexdigest()
                except Exception:
                    pass
            return file_hashes
        except Exception as e:
            print(f"[SelfAudit] Error hashing source files: {e}")
            return {}

    def detect_changes(self) -> Dict:
        """Compare current state with previous state"""
        previous = self.load_previous_state()
        
        current_config_hash = self.compute_config_hash()
        current_tools_hash = self.compute_tools_hash()
        current_brains_hash = self.compute_brains_hash()
        current_source_hashes = self.compute_source_file_hashes()
        
        changes = {
            "config_changed": False,
            "tools_changed": False,
            "brains_changed": False,
            "source_changed": False,
            "changed_files_list": [],
            "first_run": not previous,
            "details": []
        }
        
        if previous:
            if previous.get("config_hash") != current_config_hash:
                changes["config_changed"] = True
                changes["details"].append("⚙️ Configuration changed (api_keys.json)")
            
            if previous.get("tools_hash") != current_tools_hash:
                changes["tools_changed"] = True
                changes["details"].append("🛠️ Tools changed (new/modified tools)")
            
            if previous.get("brains_hash") != current_brains_hash:
                changes["brains_changed"] = True
                changes["details"].append("🧠 Available brains changed")
                
            prev_hashes = previous.get("source_hashes", {})
            if prev_hashes:
                changed_files = []
                added_files = []
                deleted_files = [f for f in prev_hashes if f not in current_source_hashes]
                
                for f_name, f_hash in current_source_hashes.items():
                    if f_name not in prev_hashes:
                        added_files.append(f_name)
                    elif prev_hashes[f_name] != f_hash:
                        changed_files.append(f_name)
                
                all_changes = []
                if changed_files: all_changes.append(f"Modified: {', '.join(changed_files)}")
                if added_files:   all_changes.append(f"Added: {', '.join(added_files)}")
                if deleted_files: all_changes.append(f"Deleted: {', '.join(deleted_files)}")
                
                if all_changes:
                    changes["source_changed"] = True
                    changes["changed_files_list"] = changed_files + added_files
                    changes["details"].append("📝 Source code changed:")
                    for c in all_changes:
                        changes["details"].append(f"     - {c}")
        
        # Save current state
        self.save_current_state({
            "config_hash": current_config_hash,
            "tools_hash": current_tools_hash,
            "brains_hash": current_brains_hash,
            "source_hashes": current_source_hashes,
            "last_audit": datetime.now().isoformat()
        })
        
        return changes
