import os
import importlib.util
import inspect
from core.interface import BasePlugin

class PluginManager:
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.loaded_plugins = {}
        
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)

    def discover_plugins(self):
        """List all available DNA sequences in the plugins directory."""
        plugins = []
        for item in os.listdir(self.plugin_dir):
            if os.path.isdir(os.path.join(self.plugin_dir, item)):
                if "__init__.py" in os.listdir(os.path.join(self.plugin_dir, item)):
                    plugins.append(item)
            elif item.endswith(".py") and item != "__init__.py":
                plugins.append(item[:-3])
        return plugins

    def load_plugin(self, name):
        """Load and initialize a specific skill."""
        try:
            # Dynamic Import
            module_path = os.path.join(self.plugin_dir, f"{name}.py")
            if not os.path.exists(module_path):
                # Check for folder-based plugin
                module_path = os.path.join(self.plugin_dir, name, "__init__.py")
            
            spec = importlib.util.spec_from_file_location(name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the class that inherits from BasePlugin
            for _, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                    instance = obj(jarvis_context={}) # Context placeholder
                    instance.initialize()
                    self.loaded_plugins[name] = instance
                    print(f"[NeuralFusion] [OK] Skill Materialized: {name}")
                    return True
        except Exception as e:
            print(f"[NeuralFusion] [ERROR] Failed to materialize {name}: {e}")
        return False

    def execute_skill(self, name, action, **kwargs):
        """Invoke a skill's logic."""
        if name in self.loaded_plugins:
            return self.loaded_plugins[name].execute(action, **kwargs)
        return f"Skill {name} not loaded, sir."
