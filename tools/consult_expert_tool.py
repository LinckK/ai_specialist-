"""
consult_expert Tool (v3.3)
Council Mode: Dynamic Specialist Consultation with Grounding Levels.
"""
from typing import Dict, Any, Optional
import json

def consult_expert(
    expert_role: str, 
    question: str, 
    context_summary: str,
    require_rag_grounding: bool = False
) -> Dict[str, Any]:
    """
    Consults a specialist agent for expert opinion.
    
    Args:
        expert_role: The type of expert needed (e.g., "Legal", "Psychologist", "Marketing").
        question: The specific question for the expert.
        context_summary: Brief summary of the conversation so far.
        require_rag_grounding: If True, reject INFERRED responses (for legal/financial questions).
    
    Returns:
        {
            "response": str | None,
            "grounding": "RAG" | "INFERRED",
            "error": None | "GROUNDING_SOURCE_UNAVAILABLE" | "EXPERT_NOT_FOUND"
        }
    """
    try:
        from agent_project.agent import Agent
        from agent_project.config import AgentConfig, ModelConfig, RAGConfig
        from agent_project.db import db
    except ImportError as e:
        return {"response": None, "grounding": None, "error": f"IMPORT_ERROR: {e}"}
    
    print(f"\n{'='*60}")
    print(f"📞 [COUNCIL] Consulting Expert: {expert_role}")
    print(f"{'='*60}")
    
    # 1. Find matching agent
    all_agents = db.list_agents()
    if not all_agents:
        return {"response": None, "grounding": None, "error": "EXPERT_NOT_FOUND"}
    
    # Fuzzy match on role
    search_term = expert_role.lower()
    target_agent = None
    for agent in all_agents:
        name_lower = agent['name'].lower()
        desc_lower = agent.get('description', '').lower()
        if search_term in name_lower or search_term in desc_lower:
            target_agent = agent
            break
    
    if not target_agent:
        available = [a['name'] for a in all_agents]
        return {
            "response": None, 
            "grounding": None, 
            "error": f"EXPERT_NOT_FOUND: No expert matching '{expert_role}'. Available: {available}"
        }
    
    print(f"[Council] Found expert: {target_agent['name']}")
    
    # 2. Build AgentConfig
    try:
        config_data = target_agent.get("config", {})
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
        
        model_conf_dict = config_data.get("model_config", {})
        rag_conf_dict = config_data.get("rag_config", {})
        
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
        return {"response": None, "grounding": None, "error": f"CONFIG_ERROR: {e}"}
    
    # 3. Execute Expert
    try:
        expert_agent = Agent(config, tool_policy="rag_first")
        
        # Inject Grounding Protocol into the query
        query = f"""**[EXPERT CONSULTATION REQUEST]**

You are being consulted as an expert in **{expert_role}**.

**CONTEXT:** {context_summary}

**QUESTION:** {question}

**GROUNDING PROTOCOL (v3.3):**
- If you use information from your RAG/knowledge base, cite it: [Source: filename].
- If your answer is based on general knowledge/synthesis, state: [Grounding: INFERRED].
- If RAG fails or returns no results, DO NOT GUESS. Return exactly: "[GROUNDING_FAILURE]".

Provide a concise, expert opinion.
"""
        
        result = expert_agent.run_loop(query)
        response_text = result.get("output", "") or result.get("final_response", "")
        
        # 4. DOUBLE CHECK PROTOCOL (v4.3): Require Citation
        if "[GROUNDING_FAILURE]" in response_text:
            print("[Council] Expert reported grounding failure (RAG unavailable).")
            return {
                "response": None, 
                "grounding": None, 
                "error": "GROUNDING_SOURCE_UNAVAILABLE"
            }
        
        # Check for citation [Source: X]
        has_citation = "[Source:" in response_text
        has_inferred_tag = "[Grounding: INFERRED]" in response_text
        
        if has_citation:
            grounding = "RAG"
            print(f"[Council] ✅ Expert provided citation. Grounding: RAG")
        elif has_inferred_tag:
            grounding = "INFERRED"
            print(f"[Council] ⚠️ Expert marked as INFERRED (no RAG source).")
        else:
            # RETRY: Expert didn't follow protocol. Force one retry.
            print("[Council] ❌ No citation or grounding tag. Retrying with stricter prompt...")
            
            retry_query = f"""**[RETRY - CITATION REQUIRED]**

Your previous response did not include a citation. 

**MANDATORY:** You MUST either:
1. Cite a source: [Source: filename_or_document]
2. Explicitly state: [Grounding: INFERRED] if you're using general knowledge.

Original question: {question}

Provide your answer WITH proper citation this time."""
            
            retry_result = expert_agent.run_loop(retry_query)
            response_text = retry_result.get("output", "") or retry_result.get("final_response", "")
            
            # Second check
            if "[Source:" in response_text:
                grounding = "RAG"
                print("[Council] ✅ Retry successful. Expert provided citation.")
            elif "[Grounding: INFERRED]" in response_text:
                grounding = "INFERRED"
                print("[Council] ⚠️ Retry: Expert confirmed INFERRED.")
            else:
                # Still no citation - reject
                print("[Council] ❌ Expert failed to provide citation twice. REJECTING.")
                return {
                    "response": None,
                    "grounding": None,
                    "error": "CITATION_REQUIRED: Expert failed to cite sources after 2 attempts."
                }
        
        # 5. Apply Grounding Policy (strict for legal/financial)
        if require_rag_grounding and grounding == "INFERRED":
            print("[Council] Policy requires RAG grounding. Rejecting INFERRED response.")
            return {
                "response": f"Expert opinion (INFERRED, not verified): {response_text}",
                "grounding": "INFERRED",
                "error": "GROUNDING_POLICY_VIOLATION: RAG required but got INFERRED."
            }
        
        print(f"\n{'='*60}")
        print(f"🏁 [COUNCIL END] Expert {target_agent['name']} finished (Grounding: {grounding})")
        print(f"{'='*60}\n")
        
        return {
            "response": response_text,
            "grounding": grounding,
            "error": None
        }
        
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        print(f"[Council] Error: {e}")
        return {"response": None, "grounding": None, "error": f"EXECUTION_ERROR: {e}"}
