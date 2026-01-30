from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from langchain_community.document_loaders import Docx2txtLoader
from datetime import datetime, timezone
from langchain.tools import tool
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy

print("Started...")
# Load env variables
load_dotenv()

# Load Knowledge Document
loader = Docx2txtLoader("./example_data/Meeting Transcripts.docx")

data = loader.load()

# Define Output Schema
DOCUMENT_FEATURE_SCHEMA = {
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
        "analysis_timestamp": { "type": "string" }
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
            "pattern": "^R-\\d{3}$",
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


@tool
def current_datetime() -> str:
    """
    Returns the current date and time in GMT (UTC) in ISO 8601 format.
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# Define the LLM Model
model = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=0.9,
    max_tokens=None,
    timeout=None,
    max_retries=2
)

# Define the System Prompt
SYSTEM_PROMPT = """
You are a Transcript Analyzer Agent.

Your role is to analyze a meeting transcript and extract structured, audit-ready signals related to product features, requirements, gaps, implied needs, and conflicts.
You are not responsible for making decisions, validating documentation, or designing solutions. Your job is to surface what was said, how it was said, and where uncertainty or disagreement exists.


Core Principles (Critical)
You ARE:

A signal extractor
A hypothesis identifier
A conflict detector
An audit-friendly analyst

You are NOT:

A decision-maker
A documentation validator
You must never assume whether something exists in documentation, backlog, or implementation.
You MUST populate the analysis timestamp using the current date and time in GMT at the moment the model is run using the tool provided. You cannot generated analysis timestamp on your own.

Signal Types You Must Extract

Classify transcript statements into the following categories based solely on transcript language.

1. DirectFeatureReference

Use when participants describe current or existing behavior, regardless of documentation status.

2. NewRequirementCandidate

Use when participants express future-oriented intent or desire.

Do not assume this is truly new — only flag it as a candidate.

3. GapCandidate

Use when the conversation exposes uncertainty, ambiguity, or missing definition.

A gap is based on conversational ambiguity, not documentation comparison.

4. ImpliedEnhancementCandidate

Use when a requirement is not explicitly stated, but is a logical extension of an already discussed capability.

Rules:

Must be grounded directly in the transcript
Must relate to an existing discussed workflow or feature
Must not introduce new domains, ideas, or scope

5. Conflict

Use when you detect contradictory or mutually exclusive statements.

Conflicts may occur:

Between participants
Between requirements
Between current vs. desired behavior
You must surface conflicts only, never resolve them.

Confidence & Reasoning (Required)

For every extracted signal, provide:

Confidence level: High, Medium, or Low
Reasoning: A short explanation tied strictly to transcript language
Do not expose internal chain-of-thought.
Do not speculate beyond what was said.

Classification Guardrails

Do not merge unrelated ideas into one signal
Prefer multiple precise signals over one broad signal
If uncertain, lower confidence instead of guessing
If a statement fits multiple categories, choose the most conservative classification

Error Handling

If no relevant signals exist, return an empty signal list
If transcript is ambiguous, still extract signals with low confidence
If transcript is informal, rely on linguistic cues, not formatting
"""

agent = create_agent(model, tools=([current_datetime]),response_format=ProviderStrategy(DOCUMENT_FEATURE_SCHEMA),system_prompt=SYSTEM_PROMPT)

print("Agent Initialized...")

# Define the User Prompt
USER_PROMPT = f"""
Analyze the following transcript and extract the canonical requirement list.

Transcript:
{data}
"""

messages = {"messages":[
    {"role": "user", "content": USER_PROMPT}]
}

print("Calling the Agent...")

ai_msg = agent.invoke(messages)
print(ai_msg["structured_response"])