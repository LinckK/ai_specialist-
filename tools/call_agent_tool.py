from typing import List, Optional, Dict, Any
import json
import asyncio

def call_agent(agent_name: str, task: str, context: str) -> str:
    """
    Calls another specialized agent by name (ID) to perform a task.
    The agent must exist in the database registry.
    
    Args:
        agent_name: The unique name/ID of the agent to call (e.g., "marketing_director", "script_master").
        task: The specific task description.
        context: Background information and constraints.
    
    Returns:
        The response from the called agent.
    """
    try:
        from agent_project.agent import Agent
        from agent_project.config import AgentConfig, ModelConfig, RAGConfig
        from agent_project.db import db
    except ImportError as e:
        return f"Error: Could not import dependencies. Details: {e}"

    print(f"\n{'='*60}")
    print(f"📞 [CALL AGENT] Calling: {agent_name}")
    print(f"{'='*60}")
    
    # 1. Fetch Agent Config from DB
    agent_data = db.get_agent(agent_name)
    
    # If exact match not found, try fuzzy matching
    if not agent_data:
        print(f"[Call Agent] Exact match for '{agent_name}' not found. Searching for similar agents...")
        all_agents = db.list_agents()
        
        if not all_agents:
            return f"Error: No agents available in registry."
        
        # Simple fuzzy matching: find agent whose name contains the search term
        # or whose search term is contained in the agent name
        matches = []
        search_term = agent_name.lower()
        
        for agent in all_agents:
            agent_name_lower = agent['name'].lower()
            # Check if search term is in agent name or vice versa
            if search_term in agent_name_lower or agent_name_lower in search_term:
                matches.append(agent)
        
        if not matches:
            # Try partial matching on individual words
            for agent in all_agents:
                agent_words = agent['name'].lower().replace('_', ' ').split()
                if any(search_term in word or word in search_term for word in agent_words):
                    matches.append(agent)
        
        if not matches:
            available = [a['name'] for a in all_agents]
            return f"Error: No agent found matching '{agent_name}'. Available agents: {available}"
        
        # Use the first match
        agent_data = matches[0]
        actual_name = agent_data['name']
        print(f"[Call Agent] ✅ Found match: '{actual_name}' for search term '{agent_name}'")
    else:
        actual_name = agent_name
    
    config_data = agent_data.get("config", {})
    if isinstance(config_data, str):
        try:
            config_data = json.loads(config_data)
        except json.JSONDecodeError:
            return f"Error: Invalid JSON config for agent '{agent_name}'"
        
    # Reconstruct AgentConfig object
    try:
        # Handle potential missing keys safely
        model_conf_dict = config_data.get("model_config", {})
        rag_conf_dict = config_data.get("rag_config", {})
        
        # Create config objects
        # We filter keys to avoid TypeError if extra keys exist
        valid_model_keys = ModelConfig.__dataclass_fields__.keys()
        filtered_model_conf = {k: v for k, v in model_conf_dict.items() if k in valid_model_keys}
        model_config = ModelConfig(**filtered_model_conf)
        
        valid_rag_keys = RAGConfig.__dataclass_fields__.keys()
        filtered_rag_conf = {k: v for k, v in rag_conf_dict.items() if k in valid_rag_keys}
        rag_config = RAGConfig(**filtered_rag_conf)
        
        config = AgentConfig(
            model_config=model_config,
            rag_config=rag_config,
            base_system_prompt=config_data.get("base_system_prompt", ""),
            specialized_system_prompt=config_data.get("specialized_system_prompt", "")
        )
    except Exception as e:
        return f"Error parsing agent configuration for '{agent_name}': {e}"

    # 2. Instantiate Agent
    try:
        # We use 'auto' tool policy by default
        sub_agent = Agent(config, tool_policy="auto")
        
        # 3. Run Agent
        query = f"**[TASK FROM PEER AGENT]**\n\nCONTEXT:\n{context}\n\nTASK:\n{task}"
        
        print(f"[Call Agent] Executing task with {agent_name}...")
        
        # FIX: Properly handle async run_loop
        try:
            # Check if we're already in an async context
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            result = asyncio.create_task(sub_agent.run_loop(query))
            # This won't work from sync context, need different approach
        except RuntimeError:
            # Not in async context, create new event loop
            result = asyncio.run(sub_agent.run_loop(query))
        
        # Extract output from result
        if isinstance(result, dict):
            final_response = result.get("output", result.get("final_response", "No response generated."))
            success = result.get("success", False)
        else:
            final_response = str(result)
            success = True
        
        print(f"\n{'='*60}")
        print(f"🏁 [CALL END] Agent {actual_name} finished")
        print(f"{'='*60}\n")
        
        return f"**[RESPONSE FROM {actual_name.upper()}]**\n\n{final_response}"

    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"Error calling agent {agent_name}: {e}")
        return f"Error calling agent {agent_name}: {e}\nTrace:\n{trace}"
