"""
Notion API integration tool.
"""

import os
import requests
from typing import Optional, Dict, Any, List

NOTION_API_BASE = "https://api.notion.com/v1"

def get_notion_headers() -> Dict[str, str]:
    """Get Notion API headers with authentication."""
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        raise ValueError("NOTION_API_KEY environment variable not set")
    
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

def query_notion_database(database_id: str, filter_data: Optional[Dict] = None) -> str:
    """
    Queries a Notion database.
    
    Args:
        database_id: The Notion database ID
        filter_data: Optional filter criteria
        
    Returns:
        Query results as formatted string
    """
    try:
        headers = get_notion_headers()
        url = f"{NOTION_API_BASE}/databases/{database_id}/query"
        
        payload = {}
        if filter_data:
            payload["filter"] = filter_data
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            return "No results found in database"
        
        # Format results
        formatted = []
        for result in results:
            page_id = result.get("id", "N/A")
            properties = result.get("properties", {})
            formatted.append(f"Page ID: {page_id}")
            for prop_name, prop_data in properties.items():
                prop_type = prop_data.get("type", "unknown")
                formatted.append(f"  {prop_name} ({prop_type})")
            formatted.append("---")
        
        return "\n".join(formatted)
    except Exception as e:
        return f"Error querying Notion database: {e}"

def create_notion_page(database_id: str, properties: Dict[str, Any]) -> str:
    """
    Creates a new page in a Notion database.
    
    Args:
        database_id: The Notion database ID
        properties: Page properties to set
        
    Returns:
        Success message with page ID
    """
    try:
        headers = get_notion_headers()
        url = f"{NOTION_API_BASE}/pages"
        
        payload = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        page_data = response.json()
        page_id = page_data.get("id", "unknown")
        
        return f"Successfully created Notion page: {page_id}"
    except Exception as e:
        return f"Error creating Notion page: {e}"

def update_notion_page(page_id: str, properties: Dict[str, Any]) -> str:
    """
    Updates a Notion page.
    
    Args:
        page_id: The Notion page ID
        properties: Properties to update
        
    Returns:
        Success message
    """
    try:
        headers = get_notion_headers()
        url = f"{NOTION_API_BASE}/pages/{page_id}"
        
        payload = {"properties": properties}
        
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        
        return f"Successfully updated Notion page: {page_id}"
    except Exception as e:
        return f"Error updating Notion page: {e}"

def notion_query(database_id: str, filter_data: Optional[Dict] = None) -> str:
    """
    Query a Notion database (alias for query_notion_database).
    """
    return query_notion_database(database_id, filter_data)

def notion_create(database_id: str, properties: Dict[str, Any]) -> str:
    """
    Create a Notion page (alias for create_notion_page).
    """
    return create_notion_page(database_id, properties)

def notion_update(page_id: str, properties: Dict[str, Any]) -> str:
    """
    Update a Notion page (alias for update_notion_page).
    """
    return update_notion_page(page_id, properties)

