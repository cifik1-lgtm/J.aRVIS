import json
from pathlib import Path

def memory_manager(parameters: dict, player=None) -> str:
    action = parameters.get("action", "retrieve")
    key = parameters.get("key", "")
    value = parameters.get("value", "")
    
    base = Path(__file__).resolve().parent.parent
    memory_dir = base / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "long_term.json"
    
    try:
        if memory_file.exists():
            data = json.loads(memory_file.read_text(encoding="utf-8"))
        else:
            data = {"identity": {}, "facts": {}}
    except Exception:
        data = {"identity": {}, "facts": {}}
        
    if "facts" not in data:
        data["facts"] = {}
        
    if action == "save":
        if not key or not value:
            return "Please provide both 'key' and 'value' to save."
        data["facts"][key] = value
        memory_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
        return f"Memory saved: {key} -> {value}"
        
    elif action == "retrieve":
        if not key:
            return f"All facts: {json.dumps(data.get('facts', {}), indent=4)}"
        val = data.get("facts", {}).get(key)
        if val:
            return f"{key}: {val}"
        return f"No memory found for '{key}'."
        
    elif action == "delete":
        if key in data.get("facts", {}):
            del data["facts"][key]
            memory_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
            return f"Memory deleted: {key}"
        return f"No memory found for '{key}'."
        
    return "Invalid action. Use save, retrieve, or delete."