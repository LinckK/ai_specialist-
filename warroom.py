import os
import json
import asyncio
from typing import List, Dict, Any, TypedDict, Annotated, Union, Literal
from uuid import uuid4
from datetime import datetime
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import litellm

# Agent Runtime Imports
from agent_project.agent import Agent
from agent_project.config import AgentConfig, ModelConfig, RAGConfig, RAGPolicy
from agent_project.db import db

# --- Configuration & Prompts ---

# USER CORRECTION: Gemini 3 Pro Preview & Flash 2.5
MODEL_PRO = "gemini/gemini-3-pro-preview"
MODEL_FLASH = "gemini/gemini-2.5-flash" 

# --- Logging Helper (v6.2) ---
def log_warroom_step(step_name: str, content: str):
    """
    Appends detailed execution logs to WARROOM_DEBUG.md for full observability.
    """
    log_path = "WARROOM_DEBUG.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"## [{timestamp}] {step_name}\n\n{content}\n\n---\n\n"
    
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"[Warroom] Log Error: {e}")

# --- State Definition ---

# --- State Definition (v3.0 Dynamic) ---

class LedgerItem(TypedDict):
    id: str
    content: str
    type: str  # HARD_CONSTRAINT, ESTABLISHED_FACT, STYLE_GUIDE, DECISION
    source: str
    status: str
    timestamp: str

class WarroomState(TypedDict):
    # The Core State
    thread_id: str
    topic: str
    
    # The "Constitution"
    ledger: Annotated[List[LedgerItem], operator.add]
    
    # Warroom v3.0: Dynamic Agents & History
    active_agents: List[str] # List of Agent Names (DB Keys)
    agent_outputs: Dict[str, str] # Map: AgentName -> Draft Content (Current Round)
    conversation_history: List[Dict] # [{"role": "user", "content": "..."}, {"role": "system", "content": "Summary..."}]
    
    # The Debate Context
    mandate: str
    round_count: int
    
    # Jury
    jury_scores: List[float]
    jury_feedback: List[str]
    average_score: float
    
    # Briefings (Triangulation)
    briefings: List[str]
    
    # Logic Gates
    status: str 
    human_choice: str 
    final_artifact: str

# --- The Warroom Class ---

class Warroom:
    def __init__(self, checkpointer=None):
        self.workflow = StateGraph(WarroomState)
        self.checkpointer = checkpointer or MemorySaver()
        self._build_graph()
        self.app = self.workflow.compile(checkpointer=self.checkpointer, interrupt_before=["node_human_gate"])

    def _build_graph(self):
        self.workflow.add_node("node_genesis", self.node_genesis)
        self.workflow.add_node("node_gladiators", self.node_gladiators)
        self.workflow.add_node("node_jury", self.node_jury)
        self.workflow.add_node("node_triangulate", self.node_triangulate)
        self.workflow.add_node("node_fuser", self.node_fuser)
        self.workflow.add_node("node_human_gate", self.node_human_gate)
        self.workflow.add_node("node_executor", self.node_executor)

        self.workflow.set_entry_point("node_genesis")

        self.workflow.add_edge("node_genesis", "node_gladiators")
        self.workflow.add_edge("node_gladiators", "node_jury")
        
        self.workflow.add_conditional_edges(
            "node_jury",
            self._check_score_condition,
            {
                "continue_debate": "node_triangulate",
                "consensus_reached": "node_human_gate" 
            }
        )

        self.workflow.add_edge("node_triangulate", "node_fuser")
        self.workflow.add_edge("node_fuser", "node_gladiators") # Loop back
        self.workflow.add_edge("node_human_gate", "node_executor")
        self.workflow.add_edge("node_executor", END)

    def _check_score_condition(self, state: WarroomState):
        score = state.get("average_score", 0)
        round_count = state.get("round_count", 0)
        print(f"[Graph] Round {round_count} Score: {score:.1f}/100")
        
        if score >= 90 or round_count >= 5:
            return "consensus_reached"
        else:
            return "continue_debate"

    # --- Node 1: Genesis ---
    def node_genesis(self, state: WarroomState):
        print("\n=== WARROOM PHASE 1: GENESIS ===")
        topic = state["topic"]
        history = state.get("conversation_history", [])
        
        # Build Context from History if available
        context_str = ""
        if history:
            context_str = "\nPREVIOUS CONTEXT:\n" + "\n".join([f"{m['role']}: {m['content'][:200]}..." for m in history])

        system_prompt = """IDENTITY: You are GENESIS, the Warroom Commander.
TASK: Analyze the user request. Assign a STRATEGIC ANGLE (Lens) to each agent to tackle the problem.

PROTOCOL:
1. ANALYZE the User Input.
2. EXTRACT the Main Goal.
3. ASSIGN A UNIQUE ANGLE to each agent.
   - The Goal is shared (e.g., "Monetize").
   - The *Angle* is specific (e.g., Searcher looks for *competitor models*, Business looks for *margins*).
   - "searcher": Must use data/search to provide a "Reality Check" or "New Inspiration".
   - "marketing-director": Focus on the "Grand Offer" and Positioning.
   - "psicologist": Focus on the "Human Element".
   - "BussinesMentor": Focus on the "Numbers".

RULES:
- **SHARED GOAL:** Everyone works on the Main Mandate. 
- **UNIQUE LENS:** Give them a specific direction to look from (e.g. "Look for X to get a different overlook").
- **NO PERSONALITY OVERRIDE:** Do NOT say "Be aggressive" unless asked. Just set the Focus.

OUTPUT FORMAT (JSON):
    {
      "initial_ledger": [{"content": "...", "type": "HARD_CONSTRAINT"}],
      "genesis_plan": {
          "searcher": "ANGLE: Analyze [Goal] by finding up-to-date competitor examples...",
          "marketing-director": "ANGLE: Attack [Goal] by drafting a high-converting offer...",
          "...": "..."
      },
      "initial_mandate": "The Shared Main Objective."
    }"""
        
        response = litellm.completion(
            model=MODEL_PRO,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"TOPIC: {topic}{context_str}\n\nCreate the Commander's Plan (JSON)."}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        content = json.loads(response.choices[0].message.content)
        
        initial_ledger = []
        for item in content.get("initial_ledger", []):
            initial_ledger.append({
                "id": str(uuid4()),
                "content": item["content"],
                "type": item["type"],
                "source": "Genesis",
                "status": "ESTABLISHED",
                "timestamp": datetime.now().isoformat()
            })
            
        print(f"[Genesis] Mandate: {content.get('initial_mandate')}")
        plan_str = json.dumps(content.get('genesis_plan', {}), indent=2)
        
        # v6.2: Deep Observability
        log_warroom_step("Phase 1: Genesis", f"**MANDATE:**\n{content.get('initial_mandate')}\n\n**PLAN:**\n{plan_str}\n\n**INITIAL LEDGER:**\n{json.dumps(initial_ledger, indent=2)}")
        
        return {
            "mandate": content.get("initial_mandate", "Execute Plan"), 
            "ledger": initial_ledger,
            "genesis_plan": content.get("genesis_plan", {})
        }

    # --- Node 2: Gladiators (Dynamic N Agents) ---
    def node_gladiators(self, state: WarroomState):
        round_idx = state["round_count"] + 1
        print(f"\n=== WARROOM PHASE 2: ARENA (Round {round_idx}) ===")
        
        mandate = state["mandate"]
        ledger_items = state["ledger"]
        ledger_txt = json.dumps([{"type": i["type"], "content": i["content"]} for i in ledger_items], indent=2)
        
        # Inject History for Multi-Turn Context
        history_txt = ""
        if state.get("conversation_history"):
            history_txt = "\n**CONVERSATION HISTORY:**\n"
            for msg in state["conversation_history"]:
                history_txt += f"[{msg['role'].upper()}] {msg['content']}\n"

        user_query = f"""**WARROOM MANDATE:** {mandate}

**TRUTH LEDGER:**
{ledger_txt}
{history_txt}

**TASK:**
Execute the Mandate. Use your specific expertise and persona.
1. Consult your tools (RAG/Search) if needed.
2. Produce a high-quality output."""

        active_agents = state["active_agents"]
        import concurrent.futures

        def _run_single_gladiator(raw_agent_identifier):
            # Parse Syntax: "AgentName:ModeName" (e.g. "Business:Aggressive")
            parts = raw_agent_identifier.split(":")
            agent_name = parts[0]
            mode_name = parts[1].strip() if len(parts) > 1 else None
            
            print(f"[Arena] Activating Agent: {agent_name} (Mode: {mode_name or 'Default'})...")
            
            agent_data = db.get_agent(agent_name)
            if not agent_data: return f"ERROR: Agent {agent_name} not found."
            
            try:
                config_dict = agent_data['config']
                # Manual Rehydration
                model_cfg_data = config_dict.get('model_config', {})
                rag_cfg_data = config_dict.get('rag_config', {})
                rag_policy_data = config_dict.get('rag_policy', {})
                
                if isinstance(model_cfg_data, dict): model_config = ModelConfig.from_dict(model_cfg_data)
                else: model_config = model_cfg_data
                    
                if isinstance(rag_cfg_data, dict): rag_config = RAGConfig.from_dict(rag_cfg_data)
                else: rag_config = rag_cfg_data

                if isinstance(rag_policy_data, dict): rag_policy = RAGPolicy.from_dict(rag_policy_data)
                else: rag_policy = rag_policy_data
                
                # Apply Mode Override
                specialized_prompt = config_dict.get('specialized_system_prompt', "")
                modes_dict = config_dict.get('modes', {})
                
                if mode_name:
                    # Case-insensitive lookup
                    mode_prompt = modes_dict.get(mode_name) or modes_dict.get(mode_name.lower())
                    
                    if mode_prompt:
                         print(f"[Arena] 🎭 Applying Mode '{mode_name}' Prompt Override.")
                         specialized_prompt += f"\n\n[MODE: {mode_name.upper()}]\n{mode_prompt}"
                    else:
                         print(f"[Arena] ⚠️ Warning: Mode '{mode_name}' not found in agent config. Using default.")

                config = AgentConfig(
                    model_config=model_config,
                    rag_config=rag_config,
                    rag_policy=rag_policy,
                    base_system_prompt=config_dict.get('base_system_prompt', ""),
                    specialized_system_prompt=specialized_prompt,
                    modes=modes_dict
                )
                
                # [WARROOM OVERRIDE]
                # In the arena, Evidence is King. Force RAG usage.
                config.rag_policy.default_mode = "MANDATORY"
                
                # Apply Warroom Tool Policy (No Delegation)
                agent = Agent(config=config, tool_policy="warroom")
                
                # REFACTOR v6.0: Pass history correctly to avoid RAG Looping on past context
                # Instead of dumping history into the prompt, we pass it as conversation history
                history_list = []
                if state.get("conversation_history"):
                     # Convert State logs to Agent History format
                     for msg in state["conversation_history"]:
                         # Map roles if necessary, but "user"/"assistant" usually fine
                         # For Warroom, usually:
                         # System: Round/Context
                         # User: The Mandate/Prompt
                         # Assistant: The output
                         # We treat the shared log as "Assistant" outputs from others? 
                         # Actually, simplest is to treat previous gladiator outputs as "User" or "System" context 
                         # OR just use the distinct roles.
                         history_list.append({"role": msg["role"], "content": msg["content"]})
                
                # v7.0 FIX: GENESIS PLAN DISPATCHER (Perspective Mode)
                # Instead of a generic prompt, we look up the specific Angle for this agent.
                genesis_plan = state.get("genesis_plan", {})
                
                # Fallback: If no specific task, use the global mandate.
                assigned_angle = genesis_plan.get(agent_name, f"Apply your specific expertise to: {mandate}")
                
                # v7.0: REMOVED "Wait/Standby" Logic.
                # In Warroom, everyone fights at the same time. No waiting.
                # If Genesis says "Wait", we ignore it and execute the Angle anyway.

                # v7.0: REMOVED "role_directive". 
                # We do NOT re-explain the agent's role. We trust their DB System Prompt.
                
                turn_prompt = f"""**COMMANDER'S INTENT (GLOBAL):** {mandate}

**TRUTH LEDGER:**
{ledger_txt}

**YOUR ASSIGNED ANGLE:**
{assigned_angle}

**EXECUTION RULES:**
1. Tackle the Global Intent using your unique Angle.
2. Use your TOOLS (RAG/Search) immediately if data is needed.
3. DO NOT simulate other agents.
4. OUTPUT: High-density analysis/content only."""
                
                print(f"[Arena] 🚀 Agent {agent_name} executing angle: {assigned_angle[:50]}...")
                
                # v6.2: Observability (Prompt Log)
                log_warroom_step(f"Phase 2: Gladiator ({agent_name}) START", f"**ANGLE:**\n{assigned_angle}\n\n**FULL PROMPT:**\n{turn_prompt}")

                # v7.0: LOOP PREVENTION
                # Hard limit of 4 turns per round (User Request). 
                agent_result = agent.run_loop(turn_prompt, history=history_list, max_turns=4)
                
                output_content = agent_result["output"] if agent_result["success"] else f"Error: {agent_result['error']}"
                
                # v6.2: Observability (Result Log)
                log_warroom_step(f"Phase 2: Gladiator ({agent_name}) END", f"**OUTPUT:**\n{output_content}")
                
                return output_content
            except Exception as e:
                import traceback
                trace = traceback.format_exc()
                print(f"Agent {agent_name} Crashed: {trace}")
                
                # v6.2: Observability (Crash Log)
                log_warroom_step(f"Phase 2: Gladiator ({agent_name}) CRASH", f"**ERROR:**\n{trace}")
                
                return f"Agent {agent_name} Crashed: {e}"

        # Dynamic Thread Execution
        agent_outputs = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_agents)) as executor:
            future_map = {executor.submit(_run_single_gladiator, name): name for name in active_agents}
            for future in concurrent.futures.as_completed(future_map):
                name = future_map[future]
                try:
                    # v6.1: Thread Timeout (180s) to detect hangs
                    output = future.result(timeout=180) 
                    agent_outputs[name] = output
                    print(f"\n--- [Arena] Output from {name} ---")
                    print(f"{output[:200]}...\n(Truncated)")
                except concurrent.futures.TimeoutError:
                    error_msg = f"Agent {name} TIMED OUT (180s Limit)."
                    print(f"[Arena] ⚠️ {error_msg}")
                    log_warroom_step(f"Phase 2: Gladiator ({name}) CRASH", f"**ERROR:**\n{error_msg}")
                    agent_outputs[name] = error_msg
                except Exception as e:
                     error_msg = f"Agent {name} CRASHED: {e}"
                     print(f"[Arena] ⚠️ {error_msg}")
                     agent_outputs[name] = error_msg

        return {"agent_outputs": agent_outputs, "round_count": round_idx}

    # --- Node 3: Jury (Dynamic) ---
    def node_jury(self, state: WarroomState):
        print("\n=== WARROOM PHASE 3: JURY ===")
        # 7 Judges
        profiles = [0.1, 0.1, 0.5, 0.5, 0.5, 0.9, 0.9] 
        
        prompt = """TASK: Evaluate the Drafts from the Agents.
METRICS:
1. QUALITY (0-100): Depth, Logic, and Execution.
2. LEDGER ADHERENCE: Compliance with constraints.

OUTPUT (JSON):
{
  "best_agent": "Name of the best agent",
  "score": 0-100 (Average quality of the room),
  "critical_feedback": "Main issues to fix"
}"""
        
        # Format Inputs
        drafts_txt = ""
        for name, text in state["agent_outputs"].items():
            drafts_txt += f"\n--- AGENT: {name} ---\n{text[:1000]}...\n"

        user_content = f"LEDGER: {state['ledger']}\n\nDRAFTS:\n{drafts_txt}"
        
        import concurrent.futures

        def run_judge(temp):
            try:
                r = litellm.completion(
                    model=MODEL_FLASH,
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_content}],
                    response_format={"type": "json_object"},
                    temperature=temp
                )
                content = json.loads(r.choices[0].message.content)
                if isinstance(content, list): content = content[0] if content else {}
                return content
            except:
                return {"score": 0, "critical_feedback": "Error"}
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            res = list(executor.map(run_judge, profiles))

        valid_scores = [r.get("score", 0) for r in res if isinstance(r.get("score"), (int, float))]
        avg = sum(valid_scores)/len(valid_scores) if valid_scores else 0
            
        print(f"[Jury] Room Score: {avg:.1f} (Votes: {len(valid_scores)})")
        
        # v6.2: Deep Observability
        log_warroom_step("Phase 3: Jury", f"**SCORES:** {valid_scores}\n**AVG:** {avg:.1f}\n\n**FEEDBACK:**\n" + "\n".join(state["jury_feedback"]))
        
        return {"jury_scores": valid_scores, "jury_feedback": [r.get("critical_feedback", "") for r in res], "average_score": avg}

    # --- Node 4: Triangulate ---
    def node_triangulate(self, state: WarroomState):
        print("\n=== WARROOM PHASE 4a: TRIANGULATION ===")
        
        prompt = "Synthesize Jury Feedback into a briefing for the agents."
        jury_txt = "\n".join(state["jury_feedback"])
        
        import concurrent.futures

        def run_briefer(_):
            # Use SYNC completion
            r = litellm.completion(
                model=MODEL_FLASH,
                messages=[{"role": "system", "content": prompt}, 
                         {"role": "user", "content": f"FEEDBACK:\n{jury_txt}"}],
                temperature=0.3
            )
            return r.choices[0].message.content
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            briefings = list(executor.map(run_briefer, range(3)))

        print("[Triangulation] 3 Independent Briefs Generated.")
        return {"briefings": briefings}

    # --- Node 5: Fuser ---
    def node_fuser(self, state: WarroomState):
        print("\n=== WARROOM PHASE 4b: FUSER (Kill Shot) ===")
        
        briefings_txt = "\n---\n".join(state["briefings"])
        
        # v7.0: COMMANDER LOGIC FOR ROUND N+1
        # The Fuser acts as Genesis for the next round.
        sys_prompt = """IDENTITY: ZERO-SHOT FUSER. & TRUTH KEEPER.
TASK: 
1. Update the GLOBAL MANDATE based on Briefings.
2. EXTRACT 3-5 "NEW TRUTHS" (Axioms) from the current round's debate.
3. ASSIGN A UNIQUE ANGLE (Lens) to each agent for the NEXT ROUND (JSON Plan).

RULES:
- **SHARED GOAL:** Everyone works on the new Mandate.
- **UNIQUE LENS:** E.g. "Searcher: Find evidence for X", "Mentor: Stress-test X".
- **NO PERSONALITY OVERRIDE:** Do NOT say "Be aggressive" unless asked.

OUTPUT (JSON): 
{
  "new_mandate": "...", 
  "new_facts": [
     {"content": "...", "type": "DECISION"},
     {"content": "...", "type": "ESTABLISHED_FACT"}
  ],
  "genesis_plan": {
      "searcher": "ANGLE: ...",
      "marketing-director": "ANGLE: ...",
      "...": "..."
  }
}"""

        res = litellm.completion(
            model=MODEL_PRO,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"BRIEFINGS:\n{briefings_txt}\n\nPlan the next round."}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        content = json.loads(res.choices[0].message.content)
        
        new_items = []
        for item in content.get("new_facts", []):
            new_items.append({
                "id": str(uuid4()), "content": item["content"], "type": item.get("type", "DECISION"),
                "source": "Fuser", "status": "IMMUTABLE", "timestamp": datetime.now().isoformat()
            })
            
        print(f"[Fuser] Mandate Updated: {content.get('new_mandate', 'No change')}")
        print(f"[Fuser] New Facts Extracted: {len(new_items)}")
        
        plan_str = json.dumps(content.get('genesis_plan', {}), indent=2)
        
        # v6.2: Observability
        log_warroom_step("Phase 4: Fuser", f"**NEW MANDATE:**\n{content.get('new_mandate')}\n\n**NEW PLAN:**\n{plan_str}\n\n**NEW TRUTHS ADDED:**\n{json.dumps(new_items, indent=2)}")
        
        return {
            "mandate": content.get("new_mandate", state["mandate"]), 
            "ledger": new_items,
            "genesis_plan": content.get("genesis_plan", {})
        }

    # --- Node 6: Human Gate ---
    def node_human_gate(self, state: WarroomState):
        # In v3.0, we just select the "best" output conceptually or ask user in Executor?
        # For now, let's just pick the first one or the "Best" from Jury if stored.
        # Ideally, we let the Executor synthesize the final output.
        print("\n[Gate] Consensus Reached.")
        return {}

    # --- Node 7: Executor (Conversation Manager) ---
    def node_executor(self, state: WarroomState):
        print("\n=== WARROOM PHASE 5: EXECUTOR (Synthesis) ===")
        
        # 1. Synthesize the Multi-Agent Output
        drafts = "\n".join([f"{k}: {v}" for k,v in state["agent_outputs"].items()])
        
        sys_prompt = """IDENTITY: You are the CONVERSATION MANAGER.
TASK: Synthesize the outputs from multiple agents into a single coherent response for the user.
Do not lose key details. Maintain the 'Warroom' tone."""
        
        res = litellm.completion(
            model=MODEL_PRO,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"DRAFTS:\n{drafts}\n\nLEDGER:\n{state['ledger']}"}
            ],
            temperature=0.1
        )
        final_text = res.choices[0].message.content
        
        # v6.2: Observability
        log_warroom_step("Phase 5: Executor", f"**FINAL ARTIFACT:**\n{final_text}")
        
        return {"final_artifact": final_text}
