from typing_extensions import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_community.document_loaders import Docx2txtLoader
from src.agents.util_agents.document_analyzer_agent import create_doc_analyzer_agent
from src.agents.util_agents.requirement_analyzer_agent import create_transcript_analyzer_agent
from src.agents.util_agents.epic_story_agent import create_epic_story_creator_agent
from src.agents.util_agents.intent_agent import create_intent_agent
from src.agents.util_agents.tools import create_state_tools, extract_backlog_fields
from src.agents.util_agents.backlog_analyzer_agent import create_backlog_analyzer_agent
from docx import Document
from docx.shared import Pt
from collections import defaultdict
import json
from dotenv import load_dotenv
from langgraph.graph.message import AnyMessage,add_messages
from typing import Annotated,List
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

load_dotenv()

# Graph state
class State(TypedDict):
    
    # Path to documents
    knowledge_source_path: str
    transcript_source_path: str
    
    # Artifacts
    feature_list: dict
    requirement_list: dict
    epic_story: dict
    
    # Jira
    epic_story_classified: dict
    
    # Routing and Conversation Messages
    user_intent: str
    messages:Annotated[List[AnyMessage],add_messages]
    
checkpointer = MemorySaver() # Saves state to memory by thread_id
    
#Nodes
def generate_features(state: State) -> Command[Literal["intent_router", "chat_agent_node"]]:
    
    # Load Knowledge Document
    # loader = Docx2txtLoader("./example_data/Confluence Design Document.docx")
    
    loader = Docx2txtLoader(state["knowledge_source_path"])

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
    file_path_epic = "./output/features.json"
    with open(file_path_epic, "w", encoding="utf-8") as f:
        json.dump(agent_message["structured_response"], f, indent=2, ensure_ascii=False)
        
    if (state["user_intent"]!= "Feature Extraction"):
        return Command(update={"feature_list": agent_message["structured_response"]},goto="intent_router")
    else:
        return Command(update={"feature_list": agent_message["structured_response"]},goto="chat_agent_node")

def generate_requirements(state: State) -> Command[Literal["intent_router", "chat_agent_node"]]:
    
    # Load Knowledge Document
    # loader = Docx2txtLoader("./example_data/Meeting Transcripts.docx")
    loader = Docx2txtLoader(state["transcript_source_path"])

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
    file_path_epic = "./output/requirements.json"
    with open(file_path_epic, "w", encoding="utf-8") as f:
        json.dump(agent_message["structured_response"], f, indent=2, ensure_ascii=False)
        
    if (state["user_intent"]!= "Requirement Analysis"):
        return Command(update={"requirement_list": agent_message["structured_response"]},goto="intent_router")
    else: 
        return Command(update={"requirement_list": agent_message["structured_response"]},goto="chat_agent_node")

def generate_epic_story(state: State) -> Command[Literal["intent_router", "chat_agent_node"]]:
    
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
    if(state["user_intent"]!="Epic/Story Generation"):
        return Command(update={"epic_story": agent_message["structured_response"]},goto="intent_router")
    else: 
        return Command(update={"epic_story": agent_message["structured_response"]},goto="chat_agent_node")

def export_epics_stories_to_docx(state: State):
    """
    Converts epic/story JSON output into a structured DOCX document.
    Epics and their related stories are grouped together.
    """
    print("Saving Data...")
    data = state["epic_story_classified"]
    
    document = Document()

    # -------------------------------
    # Helper: paragraph formatting
    # -------------------------------
    def add_label_value(label: str, value: str):
        p = document.add_paragraph()
        run_label = p.add_run(f"{label}: ")
        run_label.bold = True
        p.add_run(value if value else "N/A")

    # -------------------------------
    # Index stories by epic_id
    # -------------------------------
    stories_by_epic = defaultdict(list)
    for story in data.get("stories", []):
        stories_by_epic[story["epic_id"]].append(story)

    # -------------------------------
    # Epics & Stories
    # -------------------------------
    for epic in data.get("epics", []):
        # Epic Header
        document.add_heading(
            f"{epic['epic_id']} - {epic['name']}",
            level=1
        )

        add_label_value("Description", epic.get("description"))
        add_label_value("In Scope", epic.get("in_scope"))
        add_label_value("Out of Scope", epic.get("out_of_scope"))
        add_label_value("Classification", epic.get("classification"))
        if(epic.get("related_backlog_keys")):
            add_label_value("related_backlog_keys", epic.get("related_backlog_keys"))

        # Spacer
        document.add_paragraph("")

        # Stories under Epic
        for story in stories_by_epic.get(epic["epic_id"], []):
            document.add_heading(
                f"{story['story_id']} - {story['title']}",
                level=2
            )

            add_label_value("User Story", story.get("user_story"))
            add_label_value("Description", story.get("description"))
            add_label_value("Story Type", story.get("story_type"))

            # Acceptance Criteria
            p = document.add_paragraph()
            run = p.add_run("Acceptance Criteria:")
            run.bold = True
            document.add_paragraph(story.get("acceptance_criteria", "N/A"))

            # Tasks
            p = document.add_paragraph()
            run = p.add_run("Tasks:")
            run.bold = True

            tasks = story.get("tasks", "")
            if tasks:
                for task in [t.strip() for t in tasks.split(",")]:
                    document.add_paragraph(task, style="List Bullet")
            else:
                document.add_paragraph("N/A")

            # Tags
            if story.get("feature_tags"):
                add_label_value("Feature Tags", story.get("feature_tags"))

            if story.get("system_tags"):
                add_label_value("System Tags", story.get("system_tags"))

            # Traceability
            add_label_value("Traceability", story.get("traceability"))
            
            add_label_value("Classification", story.get("classification"))
            if(story.get("related_backlog_keys")):
                add_label_value("related_backlog_keys", story.get("related_backlog_keys"))

            # Spacer between stories
            document.add_paragraph("")

        # Page break after each epic
        document.add_page_break()

    # -------------------------------
    # Reasoning Log (Audit Section)
    # -------------------------------
    if data.get("reasoning_log"):
        document.add_heading("Reasoning Log (Audit Trail)", level=1)

        for entry in data["reasoning_log"]:
            document.add_heading(
                f"{entry['artifact_type']}: {entry['artifact_id']}",
                level=2
            )
            document.add_paragraph(entry.get("reasoning", "N/A"))
            
    # -------------------------------
    # Summarize Impact
    # -------------------------------
    if data.get("reasoning_log"):
        document.add_heading("Summarize Impact", level=1)

        for entry in data["reasoning_log"]:
            if(entry.get("backlog_reference")):
                document.add_heading(
                    f"{entry['artifact_type']}: {entry['artifact_id']}",
                    level=2
                )
                add_label_value("Backlog Reference", entry.get("backlog_reference"))
                document.add_paragraph(entry.get("impact", "N/A"))

    # -------------------------------
    # Save file
    # -------------------------------
    document.save("./output/Epic_Story_Classified.docx")
    
    file_path_epic = "./output/epic_story.json"
    with open(file_path_epic, "w", encoding="utf-8") as f:
        json.dump(state["epic_story"], f, indent=2, ensure_ascii=False)

def intent_agent_node(state: State):
    
    agent = create_intent_agent()
    # print(state["messages"])
    response = agent.invoke(
        {"messages": state["messages"]},
    )
    
    # Return updated messages
    return {"user_intent": response["structured_response"]["step"]}

def intent_router(state: State) -> Command[Literal["generate_features", "generate_requirements", "generate_epic_story", "generate_classified_artifacts_node", "export_epics_stories_to_docx", "chat_agent_node"]]:
    if state["user_intent"] == "Feature Extraction":
        return Command(goto="generate_features")
    elif state["user_intent"] == "Requirement Analysis":
        return Command(goto="generate_requirements")
    elif state["user_intent"] == "Epic/Story Generation":
        if(not state.get('feature_list')):
            return Command(goto="generate_features")
        elif(not state.get('requirement_list')):
            return Command(goto="generate_requirements")
        else:
            return Command(goto="generate_epic_story")
    elif state["user_intent"] == "Save Epic/Story":
        return Command(goto="export_epics_stories_to_docx")
    elif state["user_intent"] == "Analyze Backlog":
        if(not state.get('feature_list')):
            return Command(goto="generate_features")
        elif(not state.get('requirement_list')):
            return Command(goto="generate_requirements")
        elif(not state.get('epic_story')):
            return Command(goto="generate_epic_story")
        else:
            return Command(goto="generate_classified_artifacts_node")
    elif state["user_intent"] == "No Intent":
        return Command(goto="chat_agent_node")

def chat_agent_node(state: State):
    
    model = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.5,
        max_tokens=None,
        timeout=None,
        max_retries=2
    )
    
    user_intent = state["user_intent"]
    
    SYSTEM_PROMPT = f"""
    System Scope: You are a helpful assistant who can retrieve artifacts and answer questions based on those artifacts. Assume that the system has generated the artifacts before your call and use the provided tools as you see fit.
    
    You retrieve artifacts from the state based on the user's intent using the available tools.
    Your predecessor nodes can also save files. If user is requesting to save files, say that it is already saved.
    Present retrieved artifacts exactly as they are, without modifying their content, in a clear and readable format.

    If no specific intent is detected, respond conversationally only within the defined scope of the system and do not introduce information or actions outside that scope.
    User Intent: {user_intent}
    """
    
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=create_state_tools(state),
    )
    
    response = agent.invoke(
        {"messages": state["messages"]},
    )
    
    return {"messages": response["messages"]}
    
def generate_classified_artifacts_node(state: State):
    
    extracted_backlog = extract_backlog_fields()
    
    epic_story = {
        "epics": state['epic_story']['epics'],
        "stories": state['epic_story']['stories']
    }
    
    USER_PROMPT = f"""
    Analyze the following backlog against generated epics and stories.

    Extracted Backlogs:
    {extracted_backlog}
    
    Generates Epics and Stories:
    {epic_story}
    """

    messages = {"messages":[
        {"role": "user", "content": USER_PROMPT}]
    }

    print("Generating Classified Epics and Stories...")
    agent = create_backlog_analyzer_agent()
    agent_message = agent.invoke(messages)
    file_path_epic = "./output/epic_story_classified.json"
    with open(file_path_epic, "w", encoding="utf-8") as f:
        json.dump(agent_message["structured_response"], f, indent=2, ensure_ascii=False)
    return {"epic_story_classified": agent_message["structured_response"]}
    
# Build workflow
parallel_builder = StateGraph(State)

# Add nodes
parallel_builder.add_node("generate_features", generate_features)
parallel_builder.add_node("generate_requirements", generate_requirements)
parallel_builder.add_node("generate_epic_story", generate_epic_story)
parallel_builder.add_node("export_epics_stories_to_docx", export_epics_stories_to_docx)

# Add edges to connect nodes
parallel_builder.add_edge(START, "generate_features")
parallel_builder.add_edge(START, "generate_requirements")
parallel_builder.add_edge("generate_features", "generate_epic_story")
parallel_builder.add_edge("generate_requirements", "generate_epic_story")
parallel_builder.add_edge("generate_epic_story", "export_epics_stories_to_docx")
parallel_builder.add_edge("export_epics_stories_to_docx", END)
# parallel_workflow = parallel_builder.compile(name = "Epic Story Generator Graph")

# Add nodes to chatbot
chat_builder = StateGraph(State)
chat_builder.add_node("intent_agent_node",intent_agent_node)
chat_builder.add_node("generate_features", generate_features)
chat_builder.add_node("generate_requirements", generate_requirements)
chat_builder.add_node("generate_epic_story", generate_epic_story)
chat_builder.add_node("export_epics_stories_to_docx", export_epics_stories_to_docx)
chat_builder.add_node("chat_agent_node", chat_agent_node)
chat_builder.add_node("generate_classified_artifacts_node",generate_classified_artifacts_node)
chat_builder.add_node("intent_router",intent_router)

# Add edges to connect nodes
chat_builder.add_edge(START, "intent_agent_node")
# chat_builder.add_conditional_edges(
#     "intent_agent_node",
#     intent_router,
#     {
#         "generate_features": "generate_features",
#         "generate_requirements": "generate_requirements",
#         "generate_epic_story": "generate_epic_story",
#         "export_epics_stories_to_docx": "export_epics_stories_to_docx",
#         "generate_classified_artifacts_node": "generate_classified_artifacts_node",
#         "chat_agent_node": "chat_agent_node"
#     },
# )
chat_builder.add_edge("intent_agent_node", "intent_router")
# chat_builder.add_edge("generate_features", "chat_agent_node")
# chat_builder.add_edge("generate_requirements", "chat_agent_node")
# chat_builder.add_edge("generate_epic_story", "chat_agent_node")
chat_builder.add_edge("export_epics_stories_to_docx", "chat_agent_node")
chat_builder.add_edge("generate_classified_artifacts_node", "chat_agent_node")
chat_builder.add_edge("chat_agent_node", END)
chat_flow = chat_builder.compile(checkpointer=checkpointer)

# Invoke
# state = parallel_workflow.invoke({})
# print("Process Completed.")