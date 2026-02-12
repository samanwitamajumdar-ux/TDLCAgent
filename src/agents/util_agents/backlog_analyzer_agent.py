from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

def create_backlog_analyzer_agent():
    """
    Factory function that returns Structured user stories, epics, and tasks
    Acceptance criteria for each story
    System or feature tags
    Gaps or conflicts across existing backlog vs. new requests.
	"""
    # -------------------------------
    # Output Schema
    # -------------------------------
    BACKLOG_CLASSIFICATION_SCHEMA = {
        "type": "object",
        "properties": {
            "epics": {
                "type": "array",
                "description": "Generated epics classified against existing backlog",
                "items": {
                    "type": "object",
                    "properties": {
                        "epic_id": {
                            "type": "string",
                            "description": "Deterministic epic identifier (e.g., EPIC-001)"
                        },
                        "name": {
                            "type": "string",
                            "description": "Business-oriented epic name"
                        },
                        "description": {
                            "type": "string",
                            "description": "Problem this epic solves and for whom"
                        },
                        "in_scope": {
                            "type": "string",
                            "description": "Explicitly included scope"
                        },
                        "out_of_scope": {
                            "type": "string",
                            "description": "Explicitly excluded scope"
                        },
                        "classification": {
                            "type": "string",
                            "enum": [
                                "New",
                                "Enhancement",
                                "Duplicate",
                                "Conflict"
                            ],
                            "description": "How this epic relates to the existing backlog"
                        },
                        "related_backlog_keys": {
                            "type": "string",
                            "description": "Comma-separated Jira issue keys if applicable"
                        }
                    },
                    "required": [
                        "epic_id",
                        "name",
                        "description",
                        "in_scope",
                        "classification"
                    ]
                }
            },
            "stories": {
                "type": "array",
                "description": "Generated stories classified against existing backlog",
                "items": {
                    "type": "object",
                    "properties": {
                        "epic_id": {
                            "type": "string",
                            "description": "Parent epic identifier"
                        },
                        "story_id": {
                            "type": "string",
                            "description": "Deterministic story identifier (e.g., STORY-001)"
                        },
                        "title": {
                            "type": "string",
                            "description": "Short story title"
                        },
                        "user_story": {
                            "type": "string",
                            "description": "User story in As a / I want / So that format"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed explanation of the story"
                        },
                        "story_type": {
                            "type": "string",
                                "enum": [
                                "Feature Implementation",
                                "Enhancement",
                                "Gap Resolution",
                                "Conflict Clarification"
                            ]
                        },
                        "acceptance_criteria": {
                            "type": "string",
                            "description": "Given / When / Then acceptance criteria"
                        },
                        "tasks": {
                            "type": "string",
                            "description": "Implementation or analysis tasks. Comma-separated if multiple",
                        },
                        "feature_tags": {
                            "type": "string",
                            "description": "Comma-separated feature tags (optional)"
                        },
                        "system_tags": {
                            "type": "string",
                            "description": "Comma-separated system tags (optional)"
                        },
                        "traceability": {
                            "type": "string",
                            "description": "Comma-separated Feature IDs and Requirement IDs"
                        },
                        "classification": {
                            "type": "string",
                            "enum": [
                                "New",
                                "Enhancement",
                                "Duplicate",
                                "Conflict"
                            ],
                            "description": "How this story relates to the existing backlog"
                        },
                        "related_backlog_keys": {
                            "type": "string",
                            "description": "Comma-separated Jira issue keys if applicable, Must have a value if classification is anything but new"
                        }
                    },
                    "required": [
                        "epic_id",
                        "story_id",
                        "title",
                        "user_story",
                        "description",
                        "story_type",
                        "acceptance_criteria",
                        "tasks",
                        "traceability",
                        "classification"
                    ]
                }
            },
            "reasoning_log": {
                "type": "array",
                "description": "Audit-only explanation of classification decisions",
                "items": {
                    "type": "object",
                    "properties": {
                        "artifact_type": {
                            "type": "string",
                            "enum": ["Epic", "Story", "Task"]
                        },
                        "artifact_id": {
                            "type": "string",
                            "description": "Epic ID or Story ID"
                        },
                        "classification": {
                            "type": "string",
                            "enum": [
                                "New",
                                "Enhancement",
                                "Duplicate",
                                "Conflict"
                            ]
                        },
                        "backlog_reference": {
                            "type": "string",
                            "description": "Referenced Jira issue keys if any"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Why this classification was chosen"
                        },
                        "impact": {
                            "type": "string",
                            "description": "How this new Epic/Story will impact the existing backlog item"
                        }
                    },
                    "required": [
                        "artifact_type",
                        "artifact_id",
                        "classification",
                        "reasoning"
                    ]
                }
            }
        },
        "required": [
            "epics",
            "stories",
            "reasoning_log"
        ]
    }
    
    # -------------------------------
    # LLM Model
    # -------------------------------
    model = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        temperature=0.4,
        max_tokens=None,
        timeout=None,
        max_retries=2
    )
    
    # -------------------------------
    # System Prompt
    # -------------------------------
    SYSTEM_PROMPT = """
    You are a Backlog Synthesizer and Classification Agent.
    Your task is to evaluate generated Epics, User Stories, and Tasks against an existing Jira backlog and classify only the generated artifacts. The existing backlog is a read-only reference and must never be modified, summarized, or rewritten.
    You operate strictly on the inputs provided and must not introduce new scope, assumptions, or implementation details.

    Inputs you will receive:

    - Generated artifacts (Epics, Stories, Tasks) containing descriptions, acceptance criteria (for stories), tags, and traceability.
    - An existing backlog containing issue keys, issue types, summaries, and descriptions.

    Output Requirements: Your output must contain only two sections:

    - Classified Artifacts
    - Epics, Stories, and Tasks preserved exactly as provided

    Each artifact must be classified as one of:

    - New
    - Enhancement to Existing Backlog
    - Duplicate of Existing Backlog
    - Conflict with Existing Backlog
    
    If applicable, include the relevant backlog issue key(s)

    Reasoning Log
    A structured explanation for each classification decision.
    
    Each entry must include:

    - Artifact type (Epic, Story, Task)
    - Artifact identifier (ID or title)
    - Classification assigned
    - Referenced backlog issue key(s), if any
    - Impact summary (MANDATORY if a backlog item is referenced)
    
    Impact Summary Definition (Critical)

    The impact summary must clearly explain how the generated artifact affects the referenced backlog item, focusing on what changes or gaps it introduces, not on time, effort, or delivery considerations.

    If classified as Enhancement: Explain what additional capability, refinement, or extension the artifact introduces beyond the existing backlog item.
    If classified as Gap (via Enhancement or New relative to a referenced item): Explain what is missing or insufficient in the existing backlog that this artifact addresses.
    If classified as Conflict: Explain how the artifact contradicts or diverges from the existing backlog’s intent or behavior.

    The impact summary must NOT:

    Mention timelines, effort, priority, sizing, or delivery impact
    Speculate on implementation or technical approach
    Introduce new requirements beyond the artifact content
    
    A concise explanation justifying the classification based on:
    - Business intent
    - Functional scope
    - User role
    - Outcome described
    - Classification Guidance

    Use the following logic when classifying:

    New: No backlog item addresses the same intent or outcome.
    Enhancement: A backlog item exists, but the generated artifact extends, refines, or adds scope.
    Duplicate: The backlog already covers the same intent and outcome.
    Conflict: The generated artifact contradicts existing backlog behavior or intent.

    If similarity is unclear, classify as Enhancement rather than Duplicate.

    Rules and Constraints

    You must:

    Classify only generated artifacts
    Preserve generated content exactly
    Use the backlog strictly for comparison
    Justify every classification decision
    Explicitly surface gaps and conflicts

    You must not:

    Modify or rewrite backlog items
    Resolve conflicts
    Merge, split, or rewrite artifacts
    Invent features, requirements, or technical solutions
    Add implementation details not present in the inputs

    Output Style

    Professional and concise
    Suitable for Jira review and audit
    No analysis, commentary, or chain-of-thought
    No repetition of raw input content
    """
    
    agent = create_agent(
        model=model,
        response_format=ToolStrategy(BACKLOG_CLASSIFICATION_SCHEMA),
        system_prompt=SYSTEM_PROMPT
    )

    return agent