from typing import Dict, Any, Optional
import json

def view_agent_details(agent_name: str) -> str:
    """
    Retrieves and displays the full configuration and system prompt of a registered agent.
    Use this to understand an agent's persona and capabilities.
    
    Args:
        agent_name: The name/ID of the agent to inspect (e.g., 'Respondedor_Muie').
    
    Returns:
        A formatted string containing the agent's details and full system prompt.
    """
    try:
        from agent_project.db import db
    except ImportError as e:
        return f"Error: Could not import database. Details: {e}"

    print(f"\n🔍 [INSPECT] Fetching details for: {agent_name}")
    
    # 1. Fetch Agent from DB
    agent_data = db.get_agent(agent_name)
    
    # Fuzzy matching if not found (reuse logic from call_agent if possible, or keep simple)
    if not agent_data:
        # Simple fuzzy search
        all_agents = db.list_agents()
        matches = [a for a in all_agents if agent_name.lower() in a['name'].lower()]
        
        if not matches:
            available = [a['name'] for a in all_agents]
            return f"Error: Agent '{agent_name}' not found. Available agents: {available}"
        
        agent_data = matches[0]
        print(f"   -> Found match: {agent_data['name']}")

    # 2. Parse Config
    config_data = agent_data.get("config", {})
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON config for agent '{agent_data['name']}'"

    # 3. Format Output
    name = agent_data.get('name', 'Unknown')
    description = agent_data.get('description', 'No description')
    model = config_data.get('model_config', {}).get('litellm_model_name', 'Unknown')
    
    base_prompt = config_data.get('base_system_prompt', '')
    specialized_prompt = config_data.get('specialized_system_prompt', '')
    
    output = []
    output.append(f"🤖 AGENT: {name}")
    output.append(f"📝 DESCRIPTION: {description}")
    output.append(f"🧠 MODEL: {model}")
    output.append("-" * 40)
    output.append("📋 SPECIALIZED SYSTEM PROMPT (PERSONA):")
    if specialized_prompt:
        # Clean up for display: remove excessive whitespace/newlines
        import re
        # Collapse all whitespace sequences (including newlines) into single space
        # But try to preserve paragraph breaks if possible
        
        # First, replace non-breaking spaces
        clean_prompt = specialized_prompt.replace('\xa0', ' ')
        
        # Collapse multiple newlines to a marker
        clean_prompt = re.sub(r'\n\s*\n', '__PARAGRAPH__', clean_prompt)
        
        # Collapse all other whitespace to single space
        clean_prompt = re.sub(r'\s+', ' ', clean_prompt)
        
        # Restore paragraphs
        clean_prompt = clean_prompt.replace('__PARAGRAPH__', '\n\n')
        
        output.append(clean_prompt.strip())
    else:
        output.append("(None - uses default)")
    output.append("-" * 40)
    
    return "\n".join(output)
