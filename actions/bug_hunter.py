"""
Autonomous Bug Hunter for JARVIS
Finds, verifies, and fixes security vulnerabilities
"""

import subprocess
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

class BugHunter:
    def __init__(self, ui):
        self.ui = ui
        self.results_dir = Path.home() / "Desktop" / "bug_bounty_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Common vulnerability patterns
        self.vulnerability_patterns = {
            "sql_injection": r"(?i)(\$\w+\s*=\s*_\$GET\[|\$.*\.query\(|SELECT.*WHERE.*=.*\$)",
            "command_injection": r"(?i)(system\(|exec\(|popen\(|subprocess\.call|eval\()",
            "path_traversal": r"(?i)(\.\./|\.\.\\|open\(.*\.\.|file_get_contents\(.*\.\.)",
            "xss": r"(?i)(echo\s*\$_(GET|POST|REQUEST)\[|print\(.*\$_(GET|POST))",
            "hardcoded_secrets": r"(?i)(API_KEY|SECRET|PASSWORD|TOKEN)\s*=\s*['\"][a-zA-Z0-9]{16,}",
            "weak_crypto": r"(?i)(md5\(|sha1\(|DES\(|RC4\(|hashpw\(.*md5)",
        }
    
    def scan_repository(self, repo_path: str) -> List[Dict]:
        """Scan a local repository for vulnerabilities"""
        results = []
        
        # Run semgrep for deep analysis
        try:
            semgrep_result = subprocess.run(
                ["semgrep", "scan", "--json", repo_path],
                capture_output=True, text=True, timeout=120
            )
            if semgrep_result.returncode == 0:
                data = json.loads(semgrep_result.stdout)
                for finding in data.get("results", []):
                    results.append({
                        "type": "semgrep",
                        "rule": finding.get("check_id", "unknown"),
                        "file": finding.get("path", ""),
                        "line": finding.get("start", {}).get("line", 0),
                        "message": finding.get("extra", {}).get("message", ""),
                        "severity": finding.get("extra", {}).get("severity", "info")
                    })
        except Exception as e:
            self.ui.write_log(f"[BugHunter] semgrep failed: {e}")
        
        # Run pattern matching
        for vuln_type, pattern in self.vulnerability_patterns.items():
            grep_result = subprocess.run(
                ["grep", "-rn", pattern, repo_path, "--include=*.py", "--include=*.js", "--include=*.php"],
                capture_output=True, text=True
            )
            for line in grep_result.stdout.split('\n'):
                if line.strip():
                    results.append({
                        "type": "pattern",
                        "vulnerability": vuln_type,
                        "location": line,
                        "severity": "high" if vuln_type in ["command_injection", "hardcoded_secrets"] else "medium"
                    })
        
        return results
    
    def verify_vulnerability(self, finding: Dict) -> bool:
        """Attempt to verify if vulnerability is real (not false positive)"""
        # Use LLM to analyze the finding
        from core.llm_provider import call_local_llm # Note: adapting import based on common JARVIS structure
        
        prompt = f"""
        Analyze this potential security vulnerability and determine if it's a TRUE positive or FALSE positive.
        
        Finding: {json.dumps(finding, indent=2)}
        
        Answer with ONLY: TRUE_POSITIVE or FALSE_POSITIVE
        """
        
        response = call_local_llm(prompt, model="qwen2.5-coder:7b")
        return "TRUE_POSITIVE" in response if response else False
    
    def generate_patch(self, finding: Dict) -> str:
        """Generate a security patch using LLM"""
        from core.llm_provider import call_local_llm
        
        prompt = f"""
        Generate a secure patch for this vulnerability.
        
        Finding: {json.dumps(finding, indent=2)}
        
        Return ONLY the patch code (diff format or complete function replacement).
        Include comments explaining the security fix.
        """
        
        return call_local_llm(prompt, model="qwen2.5-coder:7b") or "# Patch generation failed"
    
    def create_pull_request(self, repo_path: str, patch: str, finding: Dict) -> bool:
        """Create a pull request with the fix"""
        try:
            # Create branch
            branch_name = f"security-fix-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=repo_path)
            
            # Apply patch
            patch_file = self.results_dir / "patch.diff"
            patch_file.write_text(patch)
            subprocess.run(["git", "apply", str(patch_file)], cwd=repo_path)
            
            # Commit and push
            subprocess.run(["git", "add", "."], cwd=repo_path)
            subprocess.run(["git", "commit", "-m", f"Security fix: {finding.get('type', 'vulnerability')}"], cwd=repo_path)
            subprocess.run(["git", "push", "origin", branch_name], cwd=repo_path)
            
            # Create PR (using GitHub CLI if available)
            pr_result = subprocess.run(
                ["gh", "pr", "create", "--title", f"Security: Fix {finding.get('type', 'vulnerability')}",
                 "--body", f"Automated security fix for potential vulnerability.\n\nFinding: {finding.get('message', '')}"],
                cwd=repo_path, capture_output=True, text=True
            )
            
            self.ui.write_log(f"[BugHunter] PR created: {pr_result.stdout}")
            return True
            
        except Exception as e:
            self.ui.write_log(f"[BugHunter] PR creation failed: {e}")
            return False

# Global instance
_hunter = None

def get_bug_hunter(ui):
    global _hunter
    if _hunter is None:
        _hunter = BugHunter(ui)
    return _hunter
