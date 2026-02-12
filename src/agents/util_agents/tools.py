from langchain.tools import tool
import json
from typing import List, Dict, Any

def create_state_tools(state: dict):
    """Factory that creates tools with access to current state."""
    
    @tool
    def get_feature_list() -> dict:
        """Get all Features."""
        return state.get("feature_list")
    
    @tool
    def get_requirement_list() -> dict:
        """Get all Requirements."""
        return state.get("requirement_list")
    
    @tool
    def get_epic_story_list() -> dict:
        """Get all Epics & Stories."""
        return state.get("epic_story")
    
    @tool
    def get_classified_epic_story_list() -> dict:
        """Get classified Epics & Stories against backlog"""
        return state.get("epic_story_classified")
    
    return [get_feature_list, get_requirement_list, get_epic_story_list,get_classified_epic_story_list]


def load_jira_backlog_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Loads Jira backlog data from a local JSON file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_backlog_fields() -> List[Dict[str, str]]:
    """
    Loads Jira backlog data from a local JSON file and Extracts only the important fields from a Jira backlog response.
    """
    
    backlog = load_jira_backlog_from_file('./example_data/jira_backlog.json')
    extracted = []

    for issue in backlog:
        fields = issue.get("fields", {})

        extracted.append({
            "issue_key": issue.get("key"),
            "issue_type": fields.get("issuetype", {}).get("name"),
            "summary": fields.get("summary"),
            "description": fields.get("description"),
        })

    return extracted