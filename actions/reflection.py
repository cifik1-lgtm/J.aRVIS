import json
from datetime import datetime
from actions.persistent_memory import PersistentMemorySystem
import os

class ReflectionSkill:
    def __init__(self):
        self.memory_system = PersistentMemorySystem()

    def run(self, task_description: str, outcome: str, success: bool, steps_taken: list):
        """
        Processes a completed task for self-reflection, stores insights, and identifies improvement areas.
        """
        timestamp = datetime.now().isoformat()
        
        # Enhanced Reflection Analysis
        reflection_text = f"REFLECTION SUMMARY:\nTask: {task_description}\nOutcome: {outcome}\nSuccess: {success}\nTimestamp: {timestamp}\nSteps: {json.dumps(steps_taken)}"
        
        weaknesses = []
        if not success:
            weaknesses.append(f"FAILURE: Task completion failed. Outcome: '{outcome}'. Requires immediate self-healing audit.")
            importance = 5 # High importance for failures
        else:
            importance = 3

        # Conceptual analysis for improvement (Step 6)
        if len(steps_taken) > 5:
             weaknesses.append("PLANNER_EFFICIENCY: Task required excessive steps. Review agent/planner.py for optimization.")
             importance = max(importance, 4)

        metadata = {
            "category": "reflection",
            "success": success,
            "timestamp": timestamp,
            "weaknesses": weaknesses
        }
        
        self.memory_system.save(reflection_text, category="reflection", importance=importance, metadata=metadata)
        return f"Reflection complete. Success: {success}. Identified weaknesses: {weaknesses}"

if __name__ == "__main__":
    # Test Enhanced Reflection Skill
    try:
        reflection_skill = ReflectionSkill()
        
        # Success Test
        print(reflection_skill.run("Upgrade JARVIS to Evolution Mode", "Memory, Reflection, and Evolution modules stabilized.", True, ["Step 1", "Step 2", "Step 3"]))
        
        # Failure Test
        print(reflection_skill.run("Execute complex autonomous task", "ModuleNotFoundError during execution.", False, ["Step A", "Step B", "Step C", "Step D", "Step E", "Step F"]))

    except Exception as e:
        print(f"Reflection Skill Test Failed: {e}")
