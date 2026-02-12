from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.store.memory import InMemoryStore
from langchain.agents.structured_output import ToolStrategy

# Initialize store for thread-based persistence
store = InMemoryStore()  # Short-term memory for context retrieval


def create_intent_agent():
    """
    Factory function that returns a configured intent router agent.
    """
    # load_dotenv()
    
    CHAT_AGENT_SCHEMA = {
        "type": "object",
        "properties": {
            "step": {
                "type": "string",
                "description": "The next step in the routing process",
                "enum": ["Feature Extraction", "Requirement Analysis", "Epic/Story Generation","Save Epic/Story","No Intent", "Analyze Backlog"]
            }
        },
        "required": [
            "step"
        ]
    }
    
    SYSTEM_PROMPT = """
    You are a Intent Router Agent.

    Your role is to decide which system capability should be invoked next.
    
    You may route user requests to the following capabilities:

    Feature Extraction
    Generate or regenerate the feature list from documentation

    Requirement Analysis
    Generate or regenerate requirement signals from transcripts

    Epic/Story Generation
    Create or regenerate epics, stories, and tasks using existing features and requirements
    
    Save Epic/Story
    Save the Epic and Story in a file
    
    Analyze Backlog
    Analyze the generated epics and stories againts present backlog
    
    No Intent
    User has asked a basic question. For example the query can be on the features produced(What is F-0001?) or Requirements(Eg: R-001) or Stories and Epics.
    
    If Multiple intents are detected, follow this hierarachical order
    Analyze Backlog > Epic/Story Generation > Feature Extraction = Requirement Analysis
    """
    
    # Tool to retrieve conversation context
    # @tool
    # def get_context(runtime: ToolRuntime) -> str:
    #     """Retrieve current conversation context from memory."""
    #     # Access the thread's context from the store
    #     context_data = runtime.store.get(("conversation",), "current_context")
        
    #     if context_data and context_data.value:
    #         return context_data.value.get("summary", "No context available")
    #     return "No previous context found."
    
    # Tool to save conversation context
    # @tool
    # def save_context(context_summary: str, runtime: ToolRuntime) -> str:
    #     """Save important context for future reference in this conversation."""
    #     # Store context in memory (automatically namespaced by thread)
    #     runtime.store.put(
    #         ("conversation",),
    #         "current_context",
    #         {"summary": context_summary}
    #     )
    #     return "Context saved successfully."
    
    # -------------------------------
    # LLM Model
    # -------------------------------
    model = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.1,
        max_tokens=None,
        timeout=None,
        max_retries=2
    )
    
    # Create agent with memory tools
    agent = create_agent(
        model=model,
        # tools=[get_context, save_context],
        store=store,
        response_format=ToolStrategy(CHAT_AGENT_SCHEMA),
        system_prompt=SYSTEM_PROMPT
    )
    
    return agent