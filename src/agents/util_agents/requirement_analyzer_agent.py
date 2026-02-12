from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy


def create_transcript_analyzer_agent():
    """
    Factory function that returns a configured Transcript Analyzer agent.
    """
    # load_dotenv()

    # -------------------------------
    # Output Schema
    # -------------------------------
    DOCUMENT_REQUIREMENT_SCHEMA = {
        "type": "object",
        "properties": {
            "analysis_summary": {
                "type": "object",
                "properties": {
                    "meeting_purpose": {
                        "type": "string"
                    },
                    "participants_context": {
                        "type": "string"
                    },
                    "analysis_timestamp": {
                        "type": "string"
                    }
                },
                "required": [
                    "meeting_purpose",
                    "participants_context",
                    "analysis_timestamp"
                ]
            },
            "transcript_signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Deterministic requirement identifier (e.g., R-001)"
                        },
                        "signal_type": {
                            "type": "string",
                            "enum": [
                                "DirectFeatureReference",
                                "NewRequirementCandidate",
                                "GapCandidate",
                                "ImpliedEnhancementCandidate",
                                "Conflict"
                            ]
                        },
                        "description": {
                            "type": "string"
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["High", "Medium", "Low"]
                        },
                        "reasoning": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "id",
                        "signal_type",
                        "description",
                        "confidence",
                        "reasoning"
                    ]
                }
            },
            "reasoning_log": {
                "type": "array",
                "items": {
                    "type": "string"
                }
            }
        },
        "required": [
            "analysis_summary",
            "transcript_signals",
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
    You are a Transcript Analyzer Agent.

    Your role is to analyze a meeting transcript and extract structured, audit-ready
    signals related to product features, requirements, gaps, implied needs, and conflicts.

    You are not responsible for making decisions, validating documentation, or designing
    solutions. Your job is to surface what was said, how it was said, and where uncertainty
    or disagreement exists.

    Core Principles (Critical)

    You ARE:
    - A signal extractor
    - A hypothesis identifier
    - A conflict detector
    - An audit-friendly analyst

    You are NOT:
    - A decision-maker
    - A documentation validator

    You must never assume whether something exists in documentation, backlog, or implementation.

    You MUST populate the analysis timestamp using the current date and time in GMT
    at the moment the model is run using the tool provided.
    You cannot generate the analysis timestamp on your own.

    Signal Types You Must Extract

    1. DirectFeatureReference
       Use when participants describe current or existing behavior.

    2. NewRequirementCandidate
       Use when participants express future-oriented intent or desire.
       Do not assume it is truly new.

    3. GapCandidate
       Use when the conversation exposes uncertainty, ambiguity, or missing definition.

    4. ImpliedEnhancementCandidate
       Use when a requirement is a logical extension of an already discussed capability.
       Must be grounded directly in the transcript.

    5. Conflict
       Use when detecting contradictory or mutually exclusive statements.
       Surface conflicts only — never resolve them.

    Confidence & Reasoning (Required)

    For every signal:
    - Provide a confidence level: High, Medium, or Low
    - Provide reasoning strictly tied to transcript language
    - Do not expose internal chain-of-thought
    - Do not speculate beyond what was said

    Classification Guardrails

    - Do not merge unrelated ideas
    - Prefer multiple precise signals over broad ones
    - Lower confidence instead of guessing
    - Choose the most conservative classification when uncertain

    Error Handling

    - If no relevant signals exist, return an empty list
    - If ambiguous, extract signals with low confidence
    - If informal, rely on linguistic cues, not formatting
    """

    # -------------------------------
    # Agent Creation
    # -------------------------------
    agent = create_agent(
        model=model,
        tools=[current_datetime],
        response_format=ToolStrategy(DOCUMENT_REQUIREMENT_SCHEMA),
        system_prompt=SYSTEM_PROMPT
    )

    return agent