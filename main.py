from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_community.document_loaders import Docx2txtLoader
from agents.document_analyzer_agent import create_doc_analyzer_agent
from agents.requirement_analyzer_agent import create_transcript_analyzer_agent
from agents.epic_story_agent import create_epic_story_creator_agent

# Graph state
class State(TypedDict):
    feature_list: dict
    requirement_list: dict
    epic_story: dict
    
#Nodes
def generate_features(state: State):
    
    # Load Knowledge Document
    loader = Docx2txtLoader("./example_data/Confluence Design Document.docx")

    data = loader.load()
    
    USER_PROMPT = f"""
    Analyze the following product documentation and extract the canonical feature list.

    DOCUMENTATION:
    {data}
    """

    messages = {"messages":[
        {"role": "user", "content": USER_PROMPT}]
    }

    print("Extracting Features from knowledge source...")
    agent = create_doc_analyzer_agent()
    agent_message = agent.invoke(messages)
    return {"feature_list": agent_message["structured_response"]}

def generate_requirements(state: State):
    
    # Load Knowledge Document
    loader = Docx2txtLoader("./example_data/Meeting Transcripts.docx")

    data = loader.load()
    
    USER_PROMPT = f"""
    Analyze the following transcript and extract the canonical requirement list.

    TRANSCRIPT:
    {data}
    """

    messages = {"messages":[
        {"role": "user", "content": USER_PROMPT}]
    }

    print("Extracting Requirements from Transcript...")
    agent = create_transcript_analyzer_agent()
    agent_message = agent.invoke(messages)
    return {"requirement_list": agent_message["structured_response"]}

def generate_epic_story(state: State):
    
    USER_PROMPT = f"""
    Analyze the following feature list and requirement list to generate epics and related stories.

    FEATURES:
    {state['feature_list']['features']}
    REQUIREMENTS:
    {state['requirement_list']['transcript_signals']}
    """
    messages = {"messages":[
        {"role": "user", "content": USER_PROMPT}]
    }

    print("Creating the Epics and Stories...")
    agent = create_epic_story_creator_agent()
    agent_message = agent.invoke(messages)
    return {"epic_story": agent_message["structured_response"]}

# Build workflow
parallel_builder = StateGraph(State)

# Add nodes
parallel_builder.add_node("generate_features", generate_features)
parallel_builder.add_node("generate_requirements", generate_requirements)
parallel_builder.add_node("generate_epic_story", generate_epic_story)

# Add edges to connect nodes
parallel_builder.add_edge(START, "generate_features")
parallel_builder.add_edge(START, "generate_requirements")
parallel_builder.add_edge("generate_features", "generate_epic_story")
parallel_builder.add_edge("generate_requirements", "generate_epic_story")
parallel_builder.add_edge("generate_epic_story", END)
parallel_workflow = parallel_builder.compile()

# Invoke
state = parallel_workflow.invoke({})
print(state["feature_list"])
print(state["requirement_list"])
print(state["epic_story"])