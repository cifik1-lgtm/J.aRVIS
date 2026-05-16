from abc import ABC, abstractmethod

class BasePlugin(ABC):
    """
    The DNA Base for all JARVIS Skills.
    """
    def __init__(self, jarvis_context):
        self.context = jarvis_context
        self.metadata = {
            "name": "Base Plugin",
            "version": "1.0.0",
            "description": "Base class for all plugins"
        }

    @abstractmethod
    def initialize(self):
        """Called when the plugin is loaded."""
        pass

    @abstractmethod
    def execute(self, action, **kwargs):
        """Execute a specific skill action."""
        pass

    @abstractmethod
    def shutdown(self):
        """Called before the plugin is unloaded."""
        pass
