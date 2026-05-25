import os
import math
from typing import Optional, Type

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import BaseTool, StructuredTool, tool
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.schema import AgentFinish, AgentAction
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

# ----------------------------------------------------------------------
# Custom Tools
# ----------------------------------------------------------------------
@tool
def calculator(expression: str) -> float:
    """Evaluate a mathematical expression. Input should be a valid Python math expression."""
    try:
        # Safe eval with limited globals
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
            "cos": math.cos, "tan": math.tan, "pi": math.pi, "e": math.e
        }
        return eval(expression, {"__builtins__": {}}, allowed_names)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def search(query: str) -> str:
    """Simulate a web search. Returns dummy information."""
    # In production, replace with actual search API
    knowledge = {
        "langchain": "LangChain is a framework for developing LLM-powered applications.",
        "python": "Python is a high-level, interpreted programming language.",
        "agent": "An AI agent is an autonomous system that perceives its environment and takes actions."
    }
    query_lower = query.lower()
    for key, value in knowledge.items():
        if key in query_lower:
            return value
    return f"Search results for '{query}': no specific information found."

class FileManagerTool(BaseTool):
    name: str = "file_manager"
    description: str = """Manage files: list directory contents, read file content, write to file.
    Input must be a dictionary with keys 'action' ('list', 'read', 'write') and 'path' (string).
    For 'write', also provide 'content' key.
    Example input: {"action": "list", "path": "."}
    """
    def _run(self, tool_input: str) -> str:
        import json
        try:
            data = json.loads(tool_input)
            action = data.get("action")
            path = data.get("path", "")
            content = data.get("content", "")
        except Exception:
            return "Invalid input. Must be a JSON object with 'action' and 'path'."
        
        if action == "list":
            try:
                items = os.listdir(path)
                return "\n".join(items) if items else "Directory is empty."
            except Exception as e:
                return f"Error listing directory: {str(e)}"
        elif action == "read":
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"Error reading file: {str(e)}"
        elif action == "write":
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully wrote to {path}"
            except Exception as e:
                return f"Error writing file: {str(e)}"
        else:
            return f"Unknown action: {action}. Use 'list', 'read', or 'write'."

# ----------------------------------------------------------------------
# Agent Setup
# ----------------------------------------------------------------------
def create_agent():
    tools = [calculator, search, FileManagerTool()]
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",  # Use a model with strong reasoning; adjust as needed
        temperature=0,
        callbacks=[StreamingStdOutCallbackHandler()],
    )
    
    # ReAct prompt template
    prompt = PromptTemplate(
        template="""You are an intelligent agent that uses tools to answer questions and perform tasks.
You have access to the following tools:
{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}""",
        input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
    )
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, max_iterations=10)
    return agent_executor

# ----------------------------------------------------------------------
# REPL Loop
# ----------------------------------------------------------------------
def repl_loop():
    agent = create_agent()
    print("Agentic AI REPL (type 'exit' to quit)")
    while True:
        user_input = input("\n> ")
        if user_input.lower() in ["exit", "quit"]:
            break
        try:
            result = agent.invoke({"input": user_input})
            print(f"Final Answer: {result['output']}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    repl_loop()