"""
RAG Policy Engine & Intent Router (v8.0).

Replaces the old scalar "Flash Judge" with a two-stage routing system:
1. Intent Classifier (Flash): Determines User Intent, Risk, and Grounding Needs.
2. Policy Engine (Deterministic): Applies Agent-Specific RAGPolicy to decide actions.
"""

import os
import json
from enum import Enum
from typing import List, Dict, Any

import litellm
from dotenv import load_dotenv

# Import RAGPolicy definition
from agent_project.config import RAGPolicy

# Load environment variables
load_dotenv()

# Ensure GEMINI_API_KEY is set
flash_key = os.getenv("GEMINIFLASH_API_KEY")
if flash_key:
    os.environ["GEMINI_API_KEY"] = flash_key


class RAGDecision(Enum):
    """Final decision on RAG usage."""
    EXECUTE = "EXECUTE"   # Force RAG
    SUGGEST = "SUGGEST"   # Prompt engineering suggestion (Context Injection)
    IGNORE = "IGNORE"     # Do not use RAG


def route_rag_intent(
    user_query: str,
    rag_policy: RAGPolicy,
    conversation_history: List[Dict] = None,
    agent_persona: str = "AI Assistant"
) -> Dict[str, Any]:
    """
    Stage 1: Classify Intent using Flash.
    Stage 2: Apply RAGPolicy rules to determine verdict and budget.
    
    Returns:
        {
            "decision": RAGDecision,
            "num_chunks": int,
            "analysis": dict (The raw Flash output)
        }
    """
    
    # --- STAGE 0: Fast Checks ---
    
    # 1. First Message Rule: Always EXECUTE if policy allows (to ground the conversation)
    if not conversation_history:
        print("[Router] First message → Defaulting to EXECUTE (if allowed)")
        # We still run classification to get proper budgeting, or just default?
        # Let's run classification to be smart, but bias towards execute.
    
    # 2. Chit-Chat (Heuristic)
    query_lower = user_query.lower().strip()
    chit_chat = ["hi", "hello", "thanks", "ok", "bye"]
    if any(query_lower == c or query_lower.startswith(c + " ") for c in chit_chat):
        print("[Router] Chit-chat detected → IGNORE")
        return {"decision": RAGDecision.IGNORE, "num_chunks": 0, "analysis": {"intent": "chit_chat"}}

    
    # --- STAGE 1: INTENT CLASSIFIER (Flash Model) ---
    
    # Prepare Context
    last_messages = conversation_history[-3:] if conversation_history else []
    context_str = "\n".join([f"{msg.get('role')}: {msg.get('content')[:100]}..." for msg in last_messages])
    
    router_system_prompt = f"""IDENTITY: You are the INTENT ROUTER for an advanced AI Agent.
YOUR GOAL: Analyze the User Query and classify it to determine Information Needs.

--- AGENT PERSONA ---
{agent_persona[:500]}...
---------------------

OUTPUT FORMAT (JSON):
{{
  "intent": "string",         // e.g., "factual_query", "creative_writing", "reasoning_task", "clarification", "chit_chat"
  "risk_level": "integer",    // 0=Safe, 1=Low, 2=Medium, 3=High (Requires absolute truth/citations)
  "requires_grounding": bool, // Does this query specific facts/data?
  "complexity": "string",     // "low", "medium", "high"
  "recommended_chunks": integer // EXACTLY 10, 20, or 30 based on depth needed.
}}

GUIDELINES:
- "risk_level": HIGH (3) if asking about Money, Health, Safety, or Specific Business Strategy.
- "recommended_chunks": 
    - 10: Simple fact check
    - 20: Standard retrieval
    - 30: Deep research / "Blue Ocean" strategy
"""

    try:
        response = litellm.completion(
            model="gemini/gemini-2.5-flash",
            messages=[
                {"role": "system", "content": router_system_prompt},
                {"role": "user", "content": f"CONTEXT:\n{context_str}\n\nQUERY: {user_query}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[Router] ⚠️ Classification Failed: {e}. Defaulting to Policy Baseline.")
        analysis = {"intent": "unknown", "risk_level": 1, "requires_grounding": True, "complexity": "medium", "recommended_chunks": 15}

    print(f"[Router] Analysis: {json.dumps(analysis)}")


    # --- STAGE 2: POLICY ENGINE (Deterministic + Model Advice) ---
    
    mode = rag_policy.default_mode
    
    # Use Model Recommendation for Budget if available, else fallback to Policy
    model_budget = analysis.get("recommended_chunks", 15)
    budget = model_budget
    
    # Decision Logic
    decision = RAGDecision.IGNORE

    if mode == "FORBIDDEN":
        decision = RAGDecision.IGNORE
        budget = 0
        print("[Router] Policy: FORBIDDEN → IGNORE")
        
    elif mode == "MANDATORY":
        decision = RAGDecision.EXECUTE
        print("[Router] Policy: MANDATORY → EXECUTE")
        
    else:
        # OPTIONAL or SUGGESTED
        if analysis.get("requires_grounding") or analysis.get("intent") in ["factual_query", "reasoning_task"]:
            decision = RAGDecision.EXECUTE
        elif mode == "SUGGESTED":
             # If suggested but not strictly required by Flash, we might still nudge
             if analysis.get("risk_level", 0) > 0:
                 decision = RAGDecision.EXECUTE
             else:
                 decision = RAGDecision.SUGGEST
        else:
            decision = RAGDecision.IGNORE
            
    # Final Sanity Check for High Risk
    if analysis.get("risk_level", 0) >= 3 and mode != "FORBIDDEN":
        decision = RAGDecision.EXECUTE
        budget = max(budget, 30) # Ensure high budget for high risk
        print("[Router] Risk Override: HIGH RISK → EXECUTE (Max Budget)")

    return {
        "decision": decision,
        "num_chunks": min(budget, 50), # Hard cap
        "analysis": analysis
    }

# Backward compatibility (if needed by tests, though we should update tests)
def evaluate_rag_need(*args, **kwargs):
    print("[DEPRECATED] evaluate_rag_need called. Please update caller to route_rag_intent.")
    return RAGDecision.IGNORE, 0
