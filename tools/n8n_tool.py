"""
Tool for triggering n8n workflows via webhooks.
Allows the agent to integrate with external automation.
"""

import requests
import json
from typing import Dict, Any, Optional

def trigger_n8n_webhook(webhook_url: str, payload: Dict[str, Any] = {}) -> str:
    """
    Triggers an n8n webhook with a JSON payload.
    
    Args:
        webhook_url: The full URL of the n8n webhook (POST).
        payload: Dictionary of data to send to the webhook.
        
    Returns:
        Response from n8n or error message.
    """
    print(f"\n--- Triggering n8n Webhook: {webhook_url} ---")
    
    try:
        headers = {
            "Content-Type": "application/json"
        }
        
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code >= 200 and response.status_code < 300:
            try:
                return f"Success: {json.dumps(response.json(), indent=2)}"
            except:
                return f"Success: {response.text}"
        else:
            return f"Error: Received status code {response.status_code}. Response: {response.text}"
            
    except Exception as e:
        return f"Error triggering webhook: {e}"
