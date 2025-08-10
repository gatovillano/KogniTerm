from langgraph.graph import StateGraph, END
from dataclasses import dataclass
from typing import List, Any
from ..interpreter import Interpreter # Assuming Interpreter is in parent directory

# Initialize the interpreter globally for now, will refactor later
interpreter = Interpreter()

@dataclass
class AgentState:
    messages: List[Any] # List of messages for the LLM
    user_message: str = ""
    gemini_response_text: str = ""
    command_to_execute: str = ""
    command_output: str = ""

def call_model_node(state: AgentState):
    """Calls the Gemini model with the user's message."""
    # interpreter.chat already adds user_message and gemini_response_text to its internal history
    gemini_response_text, command_to_execute = interpreter.chat(state.user_message)
    
    return {
        "gemini_response_text": gemini_response_text,
        "command_to_execute": command_to_execute
    }

def execute_tool_node(state: AgentState):
    """This node indicates that a tool (command) needs to be executed."""
    # We don't execute here, we just pass the command back to the main loop
    # The main loop will handle approval and actual execution
    return {} # Return an empty dictionary to update the state, ensuring a dict is returned

# Build the graph
bash_agent_graph = StateGraph(AgentState)

# Add nodes
bash_agent_graph.add_node("call_model", call_model_node)
bash_agent_graph.add_node("execute_tool", execute_tool_node)

# Set entry point
bash_agent_graph.set_entry_point("call_model")

# Add edges
bash_agent_graph.add_conditional_edges(
    "call_model",
    lambda state: "execute_tool" if state.command_to_execute else "end", # Condition based on command_to_execute
    {
        "execute_tool": "execute_tool",
        "end": END # If no command, go directly to END
    }
)
bash_agent_graph.add_edge("execute_tool", END) # After indicating tool execution, the graph ends

# Compile the graph
bash_agent_app = bash_agent_graph.compile()

# This file will also need to expose the interpreter instance
# so that the terminal can pass it to the graph.
# Or, the graph can be initialized with the interpreter.
# For now, let's keep interpreter global as it is in the original code.
