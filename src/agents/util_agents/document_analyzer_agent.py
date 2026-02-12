from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy,ToolStrategy


def create_doc_analyzer_agent():
    """
    Factory function that returns a configured Product Documentation Analyzer agent.
	"""
    # load_dotenv()

    # -------------------------------
    # Output Schema
    # -------------------------------
    DOCUMENT_FEATURE_SCHEMA = {
        "type": "object",
        "properties": {
            "document_metadata": {
                "type": "object",
                "properties": {
                    "document_name": {"type": "string"},
                    "document_version": {"type": "string"},
                    "analysis_timestamp": {"type": "string"}
                },
                "required": [
                    "analysis_timestamp"
                ]
            },
            "features": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string","description": "Deterministic feature identifier (e.g., F-0001)"},
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "Functional",
                                "Non-Functional",
                                "Integration",
                                "Data"
                            ]
                        },
                        "sub_features": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "business_rules": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "constraints": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "integrations": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "source_reference": {"type": "string"}
                    },
                    "required": [
                        "feature_id",
                        "name",
                        "description",
                        "type",
                        "source_reference"
                    ]
                }
            },
            "reasoning_log": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "related_feature_ids": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "decision": {"type": "string"},
                        "evidence": {"type": "string"}
                    },
                    "required": [
                        "decision"
                    ]
                }
            }
        },
        "required": [
            "features",
            "reasoning_log"
        ]
    }

    # -------------------------------
    # Tool: Current DateTime
    # -------------------------------
    @tool
    def current_datetime() -> str:
        """
        Returns the current date and time in GMT (UTC) in ISO 8601 format.
        """
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

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
    You are a Product Documentation Analyzer.
    Your task is to extract ALL explicitly defined product features from the provided documentation
    and convert them into a clean, structured, canonical feature list.

    Context Assumptions:
    - This is a greenfield project
    - The system is being rebuilt during a technology stack migration
    - The documentation is the single source of truth
    - Every valid product feature must exist in the documentation
    - No features should be inferred, guessed, or invented

    Critical Constraints:
    - Do NOT generate document metadata such as document name or version unless explicitly present
    - You MUST populate the analysis timestamp using the provided tool
    - All reasoning must be recorded separately in a top-level reasoning_log
    - The features output must contain only documentation-backed facts

    Rules:
    - Extract all explicitly described product features
    - Normalize names and descriptions into business-friendly language
    - Merge duplicates into a single canonical feature
    - Preserve business intent, not implementation detail
    - Capture constraints and business rules only when explicitly documented
    - Generate deterministic feature IDs starting with F-0001
    - Log all non-trivial decisions in the reasoning_log

    You MUST NOT:
    - Infer undocumented features
    - Generate enhancements or recommendations
    - Assume future functionality
    - Modify documented business intent

    Feature Qualification:
    - Pure limitations should be constraints under an existing feature
    - Create standalone features only when explicitly framed as capabilities
    """

    # -------------------------------
    # Agent Creation
    # -------------------------------
    agent = create_agent(
        model=model,
        tools=[current_datetime],
        response_format=ToolStrategy(DOCUMENT_FEATURE_SCHEMA),
        system_prompt=SYSTEM_PROMPT
    )

    return agent
