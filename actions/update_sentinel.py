# JARVIS Update Sentinel - Autonomous Version Control
import subprocess
from pathlib import Path

class UpdateSentinel:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)

    def check_for_updates(self):
        """Checks the remote repository for new commits."""
        try:
            print("[Sentinel] 🛰️ Checking cloud for new neural patterns...")
            # Fetch without merging
            subprocess.run(["git", "fetch"], cwd=str(self.base_dir), capture_output=True, check=True)
            
            # Compare local main with origin/main
            result = subprocess.run(
                ["git", "log", "main..origin/main", "--oneline"],
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                check=True
            )
            
            new_commits = result.stdout.strip().split("\n")
            if not new_commits or new_commits == ['']:
                return "Your local JARVIS is currently in sync with the Supreme Cloud, sir. No updates found."
            
            count = len(new_commits)
            report = f"### 🛰️ Cloud Update Detected\n\nThere are **{count}** new neural patches available in the cloud, sir:\n"
            for commit in new_commits[:5]:
                report += f"- {commit}\n"
            
            if count > 5:
                report += f"- ...and {count - 5} more.\n"
                
            report += "\n**Shall I initiate the 'Supreme Upgrade' protocol?**"
            return report
            
        except Exception as e:
            return f"I encountered a communication error with the cloud, sir: {e}"

    def apply_upgrade(self):
        """Performs a git pull to update the system."""
        try:
            print("[Sentinel] 🦾 Initiating Supreme Upgrade...")
            result = subprocess.run(
                ["git", "pull", "--rebase"],
                cwd=str(self.base_dir),
                capture_output=True,
                text=True,
                check=True
            )
            return f"Upgrade complete, sir! My neural pathways have been synchronized. \n\n**Output:**\n{result.stdout}"
        except Exception as e:
            return f"The upgrade was interrupted by a conflict, sir. I may need surgical intervention: {e}"

def update_sentinel(parameters, base_dir=None):
    action = parameters.get("action", "check").lower()
    sentinel = UpdateSentinel(base_dir)
    
    if action == "upgrade":
        return sentinel.apply_upgrade()
    return sentinel.check_for_updates()
