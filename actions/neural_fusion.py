# JARVIS Neural Fusion - Code Absorption Engine
import os
import shutil
import subprocess
from pathlib import Path

class NeuralFusion:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.sandbox = self.base_dir / "memory" / "fusion_sandbox"
        self.sandbox.mkdir(parents=True, exist_ok=True)

    def analyze_external_repo(self, repo_url):
        """Clones and analyzes an external repo against JARVIS core."""
        try:
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            target_path = self.sandbox / repo_name
            
            if target_path.exists():
                shutil.rmtree(target_path)
            
            print(f"[Fusion] 🧬 Cloning external DNA: {repo_name}...")
            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target_path)], check=True, capture_output=True)
            
            # Read local and remote structure
            local_files = [f.name for f in (self.base_dir / "actions").glob("*.py")]
            remote_files = [f.name for f in (target_path).rglob("*.py")]
            
            report = f"### 🧬 Neural Fusion Analysis: {repo_name}\n\n"
            report += "I have scanned the external project. Here is how it compares to my current architecture:\n\n"
            
            # This is where the LLM would normally do the deep comparison
            # For the tool response, we provide the summary of what was found
            report += f"- **External Complexity:** {len(remote_files)} source files detected.\n"
            report += "- **Potential Absorption:** Found logic relating to: "
            
            # Simple keyword matching for the report
            keywords = ["vision", "audio", "voice", "browser", "automation", "security", "gui"]
            found = []
            for f in remote_files:
                for k in keywords:
                    if k in f.lower() and k not in found: found.append(k)
            
            report += ", ".join(found) + ".\n\n"
            report += "**Sir, shall I perform a Deep Neural Comparison on these modules to see if they are superior to mine?**"
            
            return report
            
        except Exception as e:
            return f"Neural Fusion failed to scout the target, sir: {e}"

    def deep_compare(self, external_file_path, local_file_name):
        """LLM-based code comparison logic."""
        # This is called by the Planner when the user says 'Yes'
        pass

def neural_fusion(parameters, base_dir=None):
    url = parameters.get("repo_url")
    if not url: return "I need a Git URL to begin the fusion analysis, sir."
    
    fusion = NeuralFusion(base_dir)
    return fusion.analyze_external_repo(url)
