"""
n8n webhook tool for triggering n8n workflows.
"""

import requests
import os
from typing import Optional, Dict, Any

def trigger_n8n_webhook(webhook_url: str, payload: Dict[str, Any] = None) -> str:
    """
    Triggers an n8n webhook with the specified payload.
    
    Args:
        webhook_url: The n8n webhook URL
        payload: Optional JSON payload to send
        
    Returns:
        Success message or error description
    """
    try:
        if payload is None:
            payload = {}
        
        response = requests.post(webhook_url, json=payload, timeout=30)
        response.raise_for_status()
        
        return f"Successfully triggered n8n webhook. Status: {response.status_code}"
    except requests.exceptions.Timeout:
        return "Error: Webhook request timed out"
    except requests.exceptions.RequestException as e:
        return f"Error triggering webhook: {e}"

def n8n_webhook(webhook_name: str = None, webhook_url: str = None, 
                data: Dict[str, Any] = None) -> str:
    """
    Generic n8n webhook tool that can use configured webhooks or direct URLs.
    
    Args:
        webhook_name: Name of configured webhook (from environment/config)
        webhook_url: Direct webhook URL (overrides webhook_name)
        data: Payload data to send
        
    Returns:
        Result message
    """
    # If webhook_name is provided, try to get from environment
    if webhook_name and not webhook_url:
        env_key = f"N8N_WEBHOOK_{webhook_name.upper()}"
        webhook_url = os.getenv(env_key)
        if not webhook_url:
            return f"Error: Webhook '{webhook_name}' not configured. Set {env_key} environment variable."
    
    if not webhook_url:
        return "Error: Either webhook_name or webhook_url must be provided"
    
    return trigger_n8n_webhook(webhook_url, data)

