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
        """Performs a Deep Gap Analysis between JARVIS and an external project."""
        try:
            repo_name = repo_url.split("/")[-1].replace(".git", "")
            target_path = self.sandbox / repo_name
            
            if target_path.exists():
                shutil.rmtree(target_path, ignore_errors=True)
            
            print(f"[Fusion] 🧬 Scouted Target: {repo_name}...")
            subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target_path)], check=True, capture_output=True)
            
            # Map Local DNA (Actions and Core)
            local_dna = []
            for root, _, files in os.walk(self.base_dir):
                if any(x in root for x in [".git", "__pycache__", "venv", "memory"]): continue
                for f in files:
                    if f.endswith(".py"):
                        local_dna.append(f"{root.replace(str(self.base_dir), '')}\\{f}")

            # Map Target DNA
            target_dna = []
            for root, _, files in os.walk(target_path):
                if any(x in root for x in [".git", "__pycache__", "venv"]): continue
                for f in files:
                    if f.endswith(".py"):
                        target_dna.append(f"{root.replace(str(target_path), '')}\\{f}")

            # Summarize Gaps (Simple Version for now, can be sent to LLM)
            local_set = {f.split("\\")[-1] for f in local_dna}
            target_set = {f.split("\\")[-1] for f in target_dna}
            
            missing_skills = target_set - local_set
            
            report = f"### 🧬 Neural Fusion Report: {repo_name}\n\n"
            report += "Sir, I have completed the DNA comparison. Here are the 'Gaps' in my current architecture:\n\n"
            
            if missing_skills:
                report += "**Missing Capabilities Found:**\n"
                for skill in sorted(list(missing_skills))[:15]:
                    report += f"- `{skill}` (Logic I don't have)\n"
                
                report += f"\n**Analysis:** This project has {len(missing_skills)} modules that I currently lack. "
                report += "I can perform a 'Deep Extraction' on any of these to implement them into my system.\n\n"
                report += "**Shall I begin absorbing these new patterns into my 'actions/' folder?**"
            else:
                report += "Sir, I have analyzed their DNA and found nothing superior. My current architecture is already more advanced than this target project."
            
            return report
            
        except Exception as e:
            return f"Neural Fusion failed: {e}"

    def deep_compare(self, external_file_path, local_file_name):
        """LLM-based code comparison logic."""
        # This is called by the Planner when the user says 'Yes'
        pass

def neural_fusion(parameters, base_dir=None):
    url = parameters.get("repo_url")
    if not url: return "I need a Git URL to begin the fusion analysis, sir."
    
    fusion = NeuralFusion(base_dir)
    return fusion.analyze_external_repo(url)
