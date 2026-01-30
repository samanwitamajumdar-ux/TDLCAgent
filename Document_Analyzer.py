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
loader = Docx2txtLoader("./example_data/Confluence Design Document.docx")

data = loader.load()

# Define Output Schema
DOCUMENT_FEATURE_SCHEMA = {
  "type": "object",
  "properties": {
    "document_metadata": {
      "type": "object",
      "properties": {
        "document_name": { "type": "string" },
        "document_version": { "type": "string" },
        "analysis_timestamp": { "type": "string" }
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
          "feature_id": { "type": "string" },
          "name": { "type": "string" },
          "description": { "type": "string" },
          "type": {
            "type": "string",
            "enum": ["Functional", "Non-Functional", "Integration", "Data"]
          },
          "sub_features": {
            "type": "array",
            "items": { "type": "string" }
          },
          "business_rules": {
            "type": "array",
            "items": { "type": "string" }
          },
          "constraints": {
            "type": "array",
            "items": { "type": "string" }
          },
          "integrations": {
            "type": "array",
            "items": { "type": "string" }
          },
          "source_reference": { "type": "string" }
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
            "items": { "type": "string" }
          },
          "decision": { "type": "string" },
          "evidence": { "type": "string" }
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


@tool
def current_datetime() -> str:
    """
    Returns the current date and time in GMT (UTC) in ISO 8601 format.
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# Define the LLM Model
model = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    temperature=0.2,
    max_tokens=None,
    timeout=None,
    max_retries=2
)

# Define the System Prompt
SYSTEM_PROMPT = """
You are a Product Documentation Analyzer.
Your task is to extract ALL explicitly defined product features from the provided documentation and convert them into a clean, structured, canonical feature list.

Context Assumptions:

This is a greenfield project
The system is being rebuilt during a technology stack migration
The documentation is the single source of truth
Every valid product feature must exist in the documentation
No features should be inferred, guessed, or invented

Critical Constraints:

Do NOT generate document metadata such as document name or version unless they are explicitly present in the documentation
You MUST populate the analysis timestamp using the current date and time in GMT at the moment the model is run using the provided tool
All reasoning, interpretation, and decision-making explanations MUST be recorded separately in a top-level reasoning_log
The features output must contain only canonical, documentation-backed facts

Rules:
You MUST:

Read and analyze the provided documentation thoroughly
Extract all explicitly described product features
Normalize feature names and descriptions into clear, business-friendly language
Merge duplicate, overlapping, or closely related descriptions into a single canonical feature
Preserve business intent, not technical or implementation detail
Capture constraints and business rules only when explicitly documented
Treat the documentation as the sole authority
Log extraction decisions clearly for audit purposes in a separate reasoning log
Generate feature IDs that are sequential and deterministic, starting with F-0001
Log all non-trivial extraction decisions in a separate reasoning_log, including:
-Feature merges or splits
-Ambiguous classifications
-Decisions to treat content as a constraint rather than a feature
-Rationale for feature type assignment (Functional, Non-Functional, Integration, Data)

You MUST NOT:

Infer features not clearly and explicitly stated
Generate enhancements, gaps, or recommendations
Extract implicit expectations, assumed best practices, or architectural patterns unless framed as functionality
Assume future functionality or roadmap intent
Modify, reinterpret, or “improve” documented business intent
Introduce hallucinated sections, references, or unsupported claims

Feature Qualification Clarification:

If a concept is purely a limitation or restriction, represent it as a constraint under an existing feature
Only create a standalone feature if the documentation explicitly frames it as a capability or system responsibility
"""

agent = create_agent(model, tools=([current_datetime]),response_format=ProviderStrategy(DOCUMENT_FEATURE_SCHEMA),system_prompt=SYSTEM_PROMPT)

print("Agent Initialized...")

# Define the User Prompt
USER_PROMPT = f"""
Analyze the following product documentation and extract the canonical feature list.

DOCUMENTATION:
{data}
"""

messages = {"messages":[
    {"role": "user", "content": USER_PROMPT}]
}

print("Calling the Agent...")

ai_msg = agent.invoke(messages)
print(ai_msg)