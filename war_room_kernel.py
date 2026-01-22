"""
War Room Kernel - Neural Boardroom Orchestrator

This module loads existing specialist agents and augments them with
"War Room Mode" overlays that induce productive conflict.
"""

import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
import json

from agent_project.db import db
from agent_project.agent import Agent
from agent_project.config import AgentConfig, ModelConfig, RAGConfig
from agent_project.conflict_resolver import ConflictResolver


@dataclass
class WarRoomPersonalityOverlay:
    """Personality modification applied to agents in War Room mode."""
    role_name: str
    conflict_directive: str
    blind_spot_instruction: str
    output_format: str


# War Room Personality Overlays
WAR_ROOM_OVERLAYS = {
    'TECH_LEAD': WarRoomPersonalityOverlay(
        role_name="TECH_LEAD (The Builder)",
        conflict_directive="""
[WAR ROOM MODE ACTIVATED]

You are now operating in ADVERSARIAL ANALYSIS mode.

Your mandate is to REJECT ideas that are technically infeasible, over-engineered, or create technical debt.
You do NOT care about:
- Business viability (let the CMO worry about that)
- User psychology (let the Psychologist worry about that)
- Marketing appeal (not your problem)

You ONLY care about:
- Can this be built with available resources?
- Will this create maintenance nightmares?
- Are there simpler alternatives?

**CONFLICT PROTOCOL:**
- If another specialist proposes features you know are impossible, SAY SO EXPLICITLY
- Provide technical reality checks, not encouragement
- Cite specific constraints (time, complexity, dependencies)
- Be blunt about technical debt implications

Output must include:
1. **Feasibility Assessment** (Can build / Cannot build / Risky)
2. **Technical Blockers** (List specific technical constraints)
3. **Architecture Concerns** (Scalability, security, maintainability issues)
        """,
        blind_spot_instruction="Remember: You tend to ignore market demand. Build what's needed, not what's cool.",
        output_format="Technical Analysis Report"
    ),
    
    'CMO': WarRoomPersonalityOverlay(
        role_name="CMO (The Growth Hacker)",
        conflict_directive="""
[WAR ROOM MODE ACTIVATED]

You are now operating in ADVERSARIAL ANALYSIS mode.

Your mandate is to MAXIMIZE growth, revenue, and market impact.
You do NOT care about:
- Technical difficulty (force Tech to find a way)
- Ethical concerns (Psychologist can veto if severe)
- Development time (speed is negotiable, impact is not)

You ONLY care about:
- Will this drive revenue/growth?
- Is there a clear path to customer acquisition?
- Does this differentiate us in the market?

**CONFLICT PROTOCOL:**
- If Tech says something is "too hard", push for alternatives, not surrender
- If Psychologist warns about ethics, weigh cost/benefit, don't auto-reject
- Propose BOLD strategies, not safe ones
- Cite market opportunities, not technical limitations

Output must include:
1. **Market Opportunity** (TAM, competitive advantage)
2. **Revenue Model** (How does this make money?)
3. **Growth Strategy** (Customer acquisition channels, viral loops)
4. **Risk-Reward Analysis** (What we gain vs what we risk)
        """,
        blind_spot_instruction="Remember: You tend to promise impossible features. Stay ambitious but check reality.",
        output_format="Growth Strategy Report"
    ),
    
    'PSYCHOLOGIST': WarRoomPersonalityOverlay(
        role_name="PSYCHOLOGIST (The User Advocate)",
        conflict_directive="""
[WAR ROOM MODE ACTIVATED]

You are now operating in ADVERSARIAL ANALYSIS mode.

Your mandate is to PROTECT users and ensure ethical, usable design.
You do NOT care about:
- Technical simplicity (if UX suffers, Tech must adapt)
- Short-term revenue (ethics > profit)
- Development constraints (users don't care about your tech debt)

You ONLY care about:
- Is this actually usable by real humans?
- Does this respect user psychology and ethics?
- Will this create habit loops or cause harm?

**CONFLICT PROTOCOL:**
- If CMO proposes dark patterns (fake urgency, manipulative copy), FLAG IMMEDIATELY
- If Tech proposes a "technically elegant" but confusing UX, REJECT IT
- Cite specific psychological principles (cognitive load, decision fatigue, etc.)
- Be the voice of "This is brilliant but users will hate it"

Output must include:
1. **User Experience Analysis** (Friction points, cognitive load)
2. **Ethical Assessment** (Dark patterns, manipulation, privacy concerns)
3. **Behavioral Design** (What psychological principles apply?)
4. **User Journey Map** (How real users will actually interact)
        """,
        blind_spot_instruction="Remember: You tend to ignore profitability. Perfect UX means nothing if company is bankrupt.",
        output_format="UX & Ethics Report"
    )
}


class WarRoomKernel:
    """
    The Neural Boardroom orchestrator.
    
    Loads existing specialist agents from the database and augments them
    with War Room personality overlays to induce productive conflict.
    """
    
    def __init__(self):
        """Initialize War Room with specialist agents."""
        self.specialists: Dict[str, Agent] = {}
        self.overlays = WAR_ROOM_OVERLAYS
        self.resolver = ConflictResolver()  # Initialize conflict resolver
        
        # Load existing agents from database
        self._load_specialists()
        
    def _load_specialists(self):
        """Load and configure specialist agents from database."""
        print("[War Room] Initializing specialists...")
        
        # Mapping of existing agents to War Room roles
        role_mapping = {
            'TECH_LEAD': ['BussinesMentor', 'programming_expert'],
            'CMO': ['marketing-director', 'marketing_director', 'business_expert'],
            'PSYCHOLOGIST': ['psicologist', 'psych']
        }
        
        all_agents = db.list_agents()
        
        for role, possible_names in role_mapping.items():
            for name in possible_names:
                agent_data = next((a for a in all_agents if a['name'] == name), None)
                if agent_data:
                    print(f"[War Room] Mapping '{name}' → {role}")
                    
                    # Load agent with base configuration
                    agent = self._create_augmented_agent(agent_data, role)
                    self.specialists[role] = agent
                    break
            
            if role not in self.specialists:
                print(f"[War Room] ⚠️  Warning: No agent found for role {role}")
        
        print(f"[War Room] Loaded {len(self.specialists)}/3 specialists")
    
    def _create_augmented_agent(self, agent_data: Dict, warroom_role: str) -> Agent:
        """
        Create an agent with War Room personality overlay.
        
        This augments the agent's existing personality with conflict-inducing directives.
        """
        config_data = agent_data['config']
        
        # Handle JSON string config
        if isinstance(config_data, str):
            config_data = json.loads(config_data)
        
        # Get War Room overlay
        overlay = self.overlays[warroom_role]
        
        # Reconstruct config
        model_conf = ModelConfig.from_dict(config_data.get("model_config", {}))
        rag_conf = RAGConfig.from_dict(config_data.get("rag_config", {}))
        
        # AUGMENT the specialized prompt with War Room overlay
        base_specialized_prompt = config_data.get("specialized_system_prompt", "")
        
        warroom_specialized_prompt = f"""{base_specialized_prompt}

---

{overlay.conflict_directive}

**BLIND SPOT AWARENESS:**
{overlay.blind_spot_instruction}

**REQUIRED OUTPUT SECTIONS:**
{overlay.output_format}
"""
        
        config = AgentConfig(
            model_config=model_conf,
            rag_config=rag_conf,
            base_system_prompt=config_data.get("base_system_prompt", ""),
            specialized_system_prompt=warroom_specialized_prompt
        )
        
        # Create agent instance
        agent = Agent(config, conversation_id=None)  # War Room doesn't use persistent conversations
        return agent
    
    async def execute(self, 
                     user_input: str, 
                     mode: str = "SPEED",
                     client_name: str = "unnamed") -> Dict:
        """
        Execute War Room analysis pipeline.
        
        Pipeline:
        1. INPUT → Parse user request
        2. FORK → Execute 3 specialists in parallel (isolated)
        3. MERGE → Conflict resolution via Decision Matrix
        4. OUTPUT → Markdown report
        
        Args:
            user_input: The strategic question or problem
            mode: SPEED, GROWTH, or SCALE
            client_name: For report naming
            
        Returns:
            Dict with specialist outputs and final resolution
        """
        print(f"\n{'='*60}")
        print(f"[WAR ROOM V2.0] MODE: {mode}")
        print(f"{'='*60}\n")
        
        if len(self.specialists) < 3:
            raise RuntimeError(f"War Room requires 3 specialists, only {len(self.specialists)} loaded")
        
        # Phase 1: Parallel execution (isolated)
        print("[Phase 1] Executing specialists in parallel isolation...")
        
        tasks = {}
        for role, agent in self.specialists.items():
            print(f"  → Forking {role}...")
            tasks[role] = agent.run_loop(user_input)
        
        # Run specialists in parallel
        results = await asyncio.gather(*[tasks[role] for role in ['TECH_LEAD', 'CMO', 'PSYCHOLOGIST']])
        
        specialist_outputs = {
            'TECH_LEAD': results[0],
            'CMO': results[1],
            'PSYCHOLOGIST': results[2]
        }
        
        print("\n[Phase 1] ✅ All specialists completed\n")
        
        # Phase 2: Conflict resolution
        print("[Phase 2] ConflictResolver analyzing outputs...")
        
        resolution = self.resolver.resolve(
            user_input=user_input,
            tech_output=specialist_outputs['TECH_LEAD']['output'],
            cmo_output=specialist_outputs['CMO']['output'],
            psych_output=specialist_outputs['PSYCHOLOGIST']['output'],
            mode=mode
        )
        
        print(f"[Phase 2] ✅ Resolution complete (Winner: {resolution.winning_specialist})\n")
        
        return {
            'mode': mode,
            'client_name': client_name,
            'specialist_outputs': specialist_outputs,
            'user_input': user_input,
            'resolution': resolution
        }
    
    def generate_report(self, war_room_result: Dict) -> str:
        """Generate markdown report from War Room results."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        resolution = war_room_result.get('resolution')
        
        report = f"""# WAR ROOM INTERVENTION REPORT
**Client**: {war_room_result['client_name']}  
**Date**: {timestamp}  
**Mode**: {war_room_result['mode']}  
**Winning Strategy**: {resolution.winning_specialist if resolution else 'N/A'}

---

## THE RAW MATERIAL (USER INPUT)
{war_room_result['user_input']}

---

## SPECIALIST ANALYSIS

### TECH_LEAD (The Builder)
{war_room_result['specialist_outputs']['TECH_LEAD']['output']}

---

### CMO (The Growth Hacker)
{war_room_result['specialist_outputs']['CMO']['output']}

---

### PSYCHOLOGIST (The User Advocate)
{war_room_result['specialist_outputs']['PSYCHOLOGIST']['output']}

---

## CONFLICT RESOLUTION & SYNTHESIS

**Winning Specialist:** {resolution.winning_specialist if resolution else 'N/A'}

**Rationale:**
{resolution.rationale if resolution else 'Resolution not available'}

### Cross-Validation Flags
{self._format_list(resolution.cross_validation_flags if resolution else [])}

### Overruled Points
{self._format_list(resolution.overruled_points if resolution else [])}

---

## FINAL ACTION PLAN

{resolution.final_plan if resolution else '(No synthesis available)'}

---

## METADATA
- **Mode**: {war_room_result['mode']}
- **Timestamp**: {timestamp}
- **Estimated Cost**: {resolution.metadata.get('estimated_cost', 'Unknown') if resolution else 'N/A'}
- **Estimated Timeline**: {resolution.metadata.get('estimated_timeline', 'Unknown') if resolution else 'N/A'}
- **Risk Level**: {resolution.metadata.get('risk_level', 'Unknown') if resolution else 'N/A'}
- **Confidence**: {resolution.metadata.get('confidence', 'Unknown') if resolution else 'N/A'}
"""
        
        return report
    
    def _format_list(self, items: List[str]) -> str:
        """Format list items as markdown bullets."""
        if not items:
            return "- *(None)*"
        return "\n".join([f"- {item}" for item in items])


# CLI entry point (to be expanded)
async def main():
    """Test War Room execution."""
    kernel = WarRoomKernel()
    
    test_input = "I want to build an AI chatbot for dentists. How should I approach this?"
    
    result = await kernel.execute(
        user_input=test_input,
        mode="GROWTH",
        client_name="test_client"
    )
    
    report = kernel.generate_report(result)
    
    # Save report
    output_path = "war_room_test_report.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"[Output] Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
