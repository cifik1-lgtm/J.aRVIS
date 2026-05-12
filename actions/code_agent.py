"""
Code Agent - AI-powered code editing, debugging, and problem solving
Like Cursor/Claude Engineer but integrated into JARVIS
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

class CodeAgent:
    """AI-powered code analysis, editing, and debugging"""
    
    def __init__(self, workspace_dir: str = None):
        self.workspace = workspace_dir or str(Path.cwd())
        self.file_cache = {}
    
    def find_files(self, pattern: str, search_path: str = None) -> List[str]:
        """Find files matching pattern"""
        search_dir = search_path or self.workspace
        results = []
        
        for root, dirs, files in os.walk(search_dir):
            # Skip common ignore folders
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', 'venv', 'env', '.venv']]
            
            for file in files:
                if re.search(pattern, file, re.IGNORECASE):
                    full_path = os.path.join(root, file)
                    results.append(full_path)
        
        return results[:20]  # Limit results
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Read file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Write or overwrite file"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            return False
    
    def edit_file(self, file_path: str, old_text: str, new_text: str) -> bool:
        """Find and replace in file"""
        try:
            content = self.read_file(file_path)
            if content and old_text in content:
                new_content = content.replace(old_text, new_text)
                return self.write_file(file_path, new_content)
            return False
        except Exception as e:
            return False
    
    def analyze_error(self, error_text: str, file_path: str = None) -> Dict:
        """Analyze error and suggest fixes"""
        result = {
            "error": error_text,
            "file": file_path,
            "suggestions": [],
            "fixes": []
        }
        
        # Common Python error patterns
        patterns = {
            "NameError": r"NameError: name '(\w+)' is not defined",
            "ImportError": r"ImportError: No module named '(\w+)'",
            "AttributeError": r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
            "TypeError": r"TypeError: (.*?)",
            "SyntaxError": r"SyntaxError: (.*?)",
            "FileNotFoundError": r"FileNotFoundError: \[Errno 2\] No such file or directory: '(.*?)'"
        }
        
        for error_type, pattern in patterns.items():
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                result["error_type"] = error_type
                if error_type == "NameError":
                    result["suggestions"].append(f"Variable '{match.group(1)}' is not defined. Check spelling or declare it.")
                elif error_type == "ImportError":
                    result["suggestions"].append(f"Module '{match.group(1)}' is not installed. Run: pip install {match.group(1)}")
                elif error_type == "FileNotFoundError":
                    result["suggestions"].append(f"File '{match.group(1)}' not found. Check the path.")
                break
        
        # If we have the file, try to read it and suggest line-specific fixes
        if file_path and os.path.exists(file_path):
            lines = self.read_file(file_path).split('\n')
            line_numbers = re.findall(r'line (\d+)', error_text)
            for line_num in line_numbers:
                idx = int(line_num) - 1
                if 0 <= idx < len(lines):
                    result["error_line"] = lines[idx]
                    result["error_line_number"] = line_num
        
        return result
    
    def generate_fix(self, error_analysis: Dict) -> str:
        """Generate a fix suggestion based on error analysis"""
        fixes = []
        
        error_type = error_analysis.get("error_type", "")
        suggestions = error_analysis.get("suggestions", [])
        
        if error_type == "NameError":
            fixes.append(f"Add missing variable declaration or function definition.")
        elif error_type == "ImportError":
            fixes.append(f"Install missing module using pip install")
        elif error_type == "SyntaxError":
            fixes.append(f"Check the syntax around line {error_analysis.get('error_line_number', 'unknown')}")
        
        return "\n".join(fixes) if fixes else "Review the error message and check recent changes."
    
    def run_tests(self, file_path: str, test_command: str = None) -> Dict:
        """Run tests on a file"""
        result = {"success": False, "output": "", "error": ""}
        
        try:
            if file_path.endswith('.py'):
                cmd = test_command or f"python -m py_compile {file_path}"
            elif file_path.endswith('.js'):
                cmd = test_command or f"node -c {file_path}"
            else:
                cmd = test_command or f"echo 'No tests configured for this file type'"
            
            process = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            result["success"] = process.returncode == 0
            result["output"] = process.stdout
            result["error"] = process.stderr
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def get_code_structure(self, file_path: str) -> Dict:
        """Get code structure (functions, classes, imports)"""
        structure = {"imports": [], "classes": [], "functions": [], "line_count": 0}
        
        content = self.read_file(file_path)
        if not content:
            return structure
        
        lines = content.split('\n')
        structure["line_count"] = len(lines)
        
        for i, line in enumerate(lines):
            # Find imports
            if re.match(r'^import\s+', line) or re.match(r'^from\s+\S+\s+import\s+', line):
                structure["imports"].append({"line": i+1, "text": line.strip()})
            
            # Find classes
            class_match = re.match(r'^class\s+(\w+)', line)
            if class_match:
                structure["classes"].append({
                    "line": i+1,
                    "name": class_match.group(1),
                    "text": line.strip()
                })
            
            # Find functions
            func_match = re.match(r'^def\s+(\w+)\s*\(', line)
            if func_match and not line.strip().startswith('#'):
                structure["functions"].append({
                    "line": i+1,
                    "name": func_match.group(1),
                    "text": line.strip()
                })
        
        return structure


def code_agent(parameters: dict, player=None, speak=None) -> str:
    """Main handler for code agent actions"""
    agent = CodeAgent()
    action = parameters.get("action", "")
    file_path = parameters.get("file_path", "")
    pattern = parameters.get("pattern", "")
    content = parameters.get("content", "")
    old_text = parameters.get("old_text", "")
    new_text = parameters.get("new_text", "")
    error_text = parameters.get("error_text", "")
    search_path = parameters.get("search_path", "")
    test_command = parameters.get("test_command", "")
    
    result = ""
    
    if action == "find_files":
        files = agent.find_files(pattern, search_path)
        if files:
            result = f"Found {len(files)} files:\n" + "\n".join(files[:10])
            if len(files) > 10:
                result += f"\n... and {len(files)-10} more"
        else:
            result = f"No files found matching '{pattern}'"
    
    elif action == "read_file":
        if not file_path:
            result = "Error: file_path required"
        else:
            content = agent.read_file(file_path)
            if content:
                # Truncate for response
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                result = f"Content of {file_path}:\n\n{content}"
            else:
                result = f"Cannot read {file_path}"
    
    elif action == "write_file":
        if not file_path or not content:
            result = "Error: file_path and content required"
        else:
            if agent.write_file(file_path, content):
                result = f"Successfully wrote to {file_path}"
            else:
                result = f"Failed to write to {file_path}"
    
    elif action == "edit_file":
        if not file_path or not old_text or not new_text:
            result = "Error: file_path, old_text, and new_text required"
        else:
            if agent.edit_file(file_path, old_text, new_text):
                result = f"Successfully edited {file_path}"
            else:
                result = f"Failed to edit {file_path} - text not found"
    
    elif action == "analyze_error":
        if not error_text:
            result = "Error: error_text required"
        else:
            analysis = agent.analyze_error(error_text, file_path)
            result = f"Error Analysis:\nType: {analysis.get('error_type', 'Unknown')}\n"
            result += f"Suggestions: {', '.join(analysis.get('suggestions', ['None']))}\n"
            if analysis.get('error_line'):
                result += f"Line {analysis.get('error_line_number')}: {analysis.get('error_line')}\n"
            result += f"Fix: {agent.generate_fix(analysis)}"
    
    elif action == "get_structure":
        if not file_path:
            result = "Error: file_path required"
        else:
            structure = agent.get_code_structure(file_path)
            result = f"Code Structure for {file_path}:\n"
            result += f"Lines: {structure['line_count']}\n"
            result += f"Imports: {len(structure['imports'])}\n"
            result += f"Classes: {len(structure['classes'])} - {[c['name'] for c in structure['classes']]}\n"
            result += f"Functions: {len(structure['functions'])} - {[f['name'] for f in structure['functions'][:10]]}"
    
    elif action == "run_tests":
        if not file_path:
            result = "Error: file_path required"
        else:
            test_result = agent.run_tests(file_path, test_command)
            if test_result["success"]:
                result = f"Tests passed for {file_path}:\n{test_result['output'][:500]}"
            else:
                result = f"Tests failed for {file_path}:\n{test_result['error'][:500]}"
    
    elif action == "fix_file":
        """Auto-fix common issues in a file"""
        if not file_path:
            result = "Error: file_path required"
        else:
            content = agent.read_file(file_path)
            if not content:
                result = f"Cannot read {file_path}"
            else:
                # Common fixes
                fixes_applied = []
                original = content
                
                # Fix 1: Remove trailing whitespace
                if re.search(r' +$', content, re.MULTILINE):
                    content = re.sub(r' +$', '', content, flags=re.MULTILINE)
                    fixes_applied.append("Removed trailing whitespace")
                
                # Fix 2: Add newline at end of file
                if not content.endswith('\n'):
                    content += '\n'
                    fixes_applied.append("Added newline at end of file")
                
                # Fix 3: Fix common indentation issues
                if re.search(r'\t', content):
                    content = content.replace('\t', '    ')
                    fixes_applied.append("Converted tabs to spaces")
                
                if fixes_applied:
                    agent.write_file(file_path, content)
                    result = f"Applied fixes to {file_path}:\n- " + "\n- ".join(fixes_applied)
                else:
                    result = f"No automatic fixes needed for {file_path}"
    
    elif action == "search_code":
        """Search for text across code files"""
        if not pattern:
            result = "Error: pattern required"
        else:
            results = []
            files = agent.find_files("*.py", search_path)
            for f in files[:50]:  # Limit to 50 files
                content = agent.read_file(f)
                if content and pattern in content:
                    # Find line numbers
                    lines = content.split('\n')
                    matches = []
                    for i, line in enumerate(lines):
                        if pattern in line:
                            matches.append(f"  Line {i+1}: {line.strip()[:80]}")
                    if matches:
                        results.append(f"\n{f}:\n" + "\n".join(matches[:3]))
            
            if results:
                result = f"Found '{pattern}' in {len(results)} files:" + "".join(results[:5])
            else:
                result = f"No matches found for '{pattern}'"
    
    else:
        result = f"Unknown action: {action}. Available: find_files, read_file, write_file, edit_file, analyze_error, get_structure, run_tests, fix_file, search_code"
    
    if player:
        player.write_log(f"[CodeAgent] {result[:200]}")
    if speak:
        speak(result[:200])
    
    return result