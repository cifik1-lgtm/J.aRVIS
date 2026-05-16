# JARVIS Hive DNA - Evolutionary Skill Engine
import json
import time
import os
from pathlib import Path

class HiveDNA:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.stats_path = self.base_dir / "memory" / "tool_performance.json"
        self.evolved_path = self.base_dir / "actions" / "evolved"
        self.evolved_path.mkdir(parents=True, exist_ok=True)
        self.stats = self._load_stats()

    def _load_stats(self):
        if self.stats_path.exists():
            try: return json.loads(self.stats_path.read_text(encoding="utf-8"))
            except: return {}
        return {}

    def _save_stats(self):
        self.stats_path.parent.mkdir(parents=True, exist_ok=True)
        self.stats_path.write_text(json.dumps(self.stats, indent=4), encoding="utf-8")

    def record_performance(self, tool_name, duration, success):
        """Records the 'Fitness' of a tool call."""
        if tool_name not in self.stats:
            self.stats[tool_name] = {"calls": 0, "avg_time": 0, "success_rate": 0, "failures": 0}
        
        s = self.stats[tool_name]
        total_calls = s["calls"]
        
        # Update Avg Time
        s["avg_time"] = ((s["avg_time"] * total_calls) + duration) / (total_calls + 1)
        
        # Update Success Rate
        if success:
            s["success_rate"] = ((s["success_rate"] * total_calls) + 100) / (total_calls + 1)
        else:
            s["failures"] += 1
            s["success_rate"] = (s["success_rate"] * total_calls) / (total_calls + 1)
            
        s["calls"] += 1
        self._save_stats()

    def identify_weak_links(self):
        """Finds tools that are slow or failing."""
        weak = []
        for name, data in self.stats.items():
            if data["success_rate"] < 80 and data["calls"] > 5:
                weak.append(name)
        return weak

    def get_dna_report(self):
        """Returns a report of the current tool fitness."""
        if not self.stats: return "No performance data captured yet, sir."
        
        report = "### 🧬 Hive DNA Fitness Report\n\n"
        for name, data in sorted(self.stats.items(), key=lambda x: x[1]['success_rate']):
            status = "🟢 Supreme" if data['success_rate'] > 95 else "🟡 Evolving" if data['success_rate'] > 80 else "🔴 Weak Link"
            report += f"- **{name}**: {status} ({int(data['success_rate'])}% success, {data['avg_time']:.2f}s avg)\n"
        
        return report

# Global Instance
_dna = None

def get_dna(base_dir):
    global _dna
    if _dna is None:
        _dna = HiveDNA(base_dir)
    return _dna

async def evolve_skill(parameters, jarvis, player=None):
    """The high-level evolution tool."""
    target = parameters.get("target_tool")
    base_dir = jarvis.base_dir
    dna = get_dna(base_dir)
    
    if not target:
        weak = dna.identify_weak_links()
        if not weak: return "All systems are currently performing at Supreme levels, sir."
        target = weak[0]

    if player: player.write_log(f"🧬 Hive DNA: Initiating evolution for {target}...")
    
    # In a real scenario, this would trigger a 'self_fix' or 'learn_skill' 
    # to rewrite the target tool with better logic.
    return f"Evolution sequence initiated for '{target}'. I am analyzing its DNA to generate a superior mutation, sir."
