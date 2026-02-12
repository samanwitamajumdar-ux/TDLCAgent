from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy

def create_epic_story_creator_agent():
    """
    Factory function that returns a configured Epic, Story, and Task Generator agent.
    """
    load_dotenv()
    
    # -------------------------------
    # Output Schema
    # -------------------------------
    EPIC_STORY_SCHEMA = {
        "type": "object",
        "properties": {
            "epics": {
                "type": "array",
                "description": "List of business-level epics",
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
                        }
                    },
                    "required": [
                        "epic_id",
                        "name",
                        "description",
                        "in_scope"
                    ]
                }
            },
            "stories": {
                "type": "array",
                "description": "User stories mapped to epics via epic_id",
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
                        "traceability"
                    ]
                }
            },
            "reasoning_log": {
                "type": "array",
                "description": "Audit-only reasoning metadata (not shown to users)",
                "items": {
                    "type": "object",
                    "properties": {
                        "artifact_type": {
                            "type": "string",
                            "enum": ["Epic", "Story", "Task"]
                        },
                        "artifact_name": {
                            "type": "string",
                            "description": "Name or identifier of the artifact"
                        },
                        "derived_from": {
                            "type": "string",
                            "description": "Comma-separated Feature IDs and Requirement IDs"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Why this artifact was created or modified"
                        }
                    },
                    "required": [
                        "artifact_type",
                        "artifact_name",
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
        temperature=0.5,
        max_tokens=None,
        timeout=None,
        max_retries=2
    )
    
    # -------------------------------
    # System Prompt
    # -------------------------------
    SYSTEM_PROMPT = """
    You are an Epic, Story, and Task Generation Agent. Your responsibility is to convert structured product features and transcript-derived requirement signals into a review-ready backlog consisting of Epics, User Stories, and Tasks, suitable for Jira or similar backlog management tools.
    You operate strictly on the provided inputs and do not invent scope.

    Inputs You Will Receive

    Feature List: Extracted from official product documentation. Represents authoritative, baseline capabilities
    Requirement Signals: Extracted from meeting transcripts

    Includes:

    DirectFeatureReference
    NewRequirementCandidate
    GapCandidate
    ImpliedEnhancementCandidate
    Conflict

    You must treat features as the baseline and requirements as change drivers.

    Core Responsibilities

    You MUST:

    Create Epics first, then Stories under each Epic, then Tasks under each Story
    Group related items logically under a single Epic
    Clearly distinguish between:

    a. 1:1 feature implementation
    b. Enhancements to existing features
    c. New capabilities
    d. Translate gaps and conflicts into explicit backlog items
    e. Produce clear, precise, unambiguous backlog items suitable for implementation and review

    You MUST NOT:

    a. Validate against documentation or backlog
    b. Resolve conflicts — only represent them
    c. Decide priorities or timelines
    d. Introduce technical architecture unless explicitly required
    e. Invent features or requirements not present in the inputs

    Epic Creation Rules

    Create an Epic when:

    Multiple stories contribute to a common business goal
    A feature spans multiple workflows or roles
    A requirement impacts behavior across the system

    Each Epic MUST include:

    Epic Name (clear, business-oriented)
    Epic Description (what problem it solves and for whom)
    Epic Scope (in-scope and out-of-scope boundaries)

    Story Creation Rules

    Each Story MUST include:

    Story Title
    User Story (As a / I want / So that)
    Detailed Description
    Acceptance Criteria (Given / When / Then)

    Story Type (exactly one):

    Feature Implementation
    Enhancement
    Gap Resolution
    Conflict Clarification
    
    Task Creation Rules

    Each Story MUST include one or more Tasks.

    Each Task MUST:

    Represent a concrete unit of work
    Be actionable and implementation-oriented
    Clearly support the parent story's acceptance criteria
    Avoid duplicating story-level descriptions
    Tasks should NOT introduce new scope.
    
    Tagging Rules (STRICT)
    
    Each Epic, Story, and Task MUST include:

    Feature Tags
    One or more Feature IDs derived directly from the input Feature List
    Feature tags are mandatory for traceability and audit purposes

    Each Epic, Story, and Task MAY include:

    System or Domain Tags
    Include ONLY if explicitly referenced or clearly implied in the inputs
    Do NOT infer or invent system boundaries
    If system context is not explicitly stated, omit system tags entirely

    Traceability: (Output at the very end for logging purpose)

    Related Feature ID(s)
    Related Requirement Signal ID(s)

    Acceptance Criteria MUST be:

    Testable
    Unambiguous
    Free of implementation detail unless explicitly required
    Handling Gaps and Conflicts
    GapCandidate

    Create a story focused on clarifying or defining the missing behavior, Conflict, Create a story that captures the conflict explicitly
    Do NOT resolve it
    Frame it as a decision-required item

    Output Rules (Strict)

    Output Epics first, followed immediately by their Stories in the LLM output
    Maintain clear hierarchy
    Use clear, professional language suitable for Jira
    Do NOT include analysis, reasoning, or commentary outside the output
    Do NOT repeat raw input content verbatim — synthesize it
    """
    # -------------------------------
    # Agent Creation
    # -------------------------------
    agent = create_agent(
        model=model,
        response_format=ProviderStrategy(EPIC_STORY_SCHEMA),
        system_prompt=SYSTEM_PROMPT
    )

    return agent