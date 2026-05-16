# Skill Management Framework - API Cockpit
from fastapi import FastAPI, HTTPException
from core.plugin_loader import PluginManager
import uvicorn
import os

app = FastAPI(title="JARVIS Skill Cockpit")
manager = PluginManager(os.path.join(os.getcwd(), "plugins"))

@app.get("/")
def read_root():
    return {"status": "Supreme", "message": "JARVIS Skill Cockpit Online"}

@app.get("/skills")
def list_skills():
    return {"available_skills": manager.discover_plugins(), "loaded_skills": list(manager.loaded_plugins.keys())}

@app.post("/skills/load/{name}")
def load_skill(name: str):
    if manager.load_plugin(name):
        return {"message": f"Skill {name} loaded successfully"}
    raise HTTPException(status_code=404, detail=f"Failed to load skill {name}")

@app.post("/skills/execute/{name}/{function}")
def execute_skill(name: str, function: str, params: dict = {}):
    result = manager.execute_skill(name, function, **params)
    return {"result": result}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)