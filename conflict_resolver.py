"""
Conflict Resolver - The CEO Brain

Synthesizes isolated specialist outputs using cross-validation
and mode-based decision hierarchies.
"""

import json
from typing import Dict, List
import litellm
from dataclasses import dataclass


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""
    winning_specialist: str
    rationale: str
    cross_validation_flags: List[str]
    overruled_points: List[str]
    final_plan: str
    metadata: Dict
    
    def to_dict(self) -> Dict:
        return {
            'winning_specialist': self.winning_specialist,
            'rationale': self.rationale,
            'cross_validation_flags': self.cross_validation_flags,
            'overruled_points': self.overruled_points,
            'final_plan': self.final_plan,
            'metadata': self.metadata
        }


class ConflictResolver:
    """
    The CEO brain that synthesizes specialist outputs.
    
    Performs cross-validation to ensure each specialist's blind spots
    are covered by other specialists.
    """
    
    def __init__(self, model: str = "gemini/gemini-3-pro-preview"):
        """Initialize resolver with high-quality synthesis model."""
        self.model = model
    
    def resolve(self,
                user_input: str,
                tech_output: str,
                cmo_output: str,
                psych_output: str,
                mode: str) -> ResolutionResult:
        """
        Synthesize isolated outputs with cross-validation.
        
        Args:
            user_input: Original user question
            tech_output: Technical lead's analysis
            cmo_output: CMO's growth strategy
            psych_output: Psychologist's UX/ethics assessment
            mode: SPEED, GROWTH, or SCALE
            
        Returns:
            ResolutionResult with synthesized strategy
        """
        # Define mode-specific hierarchies
        system_instruction = self._get_mode_instruction(mode)
        
        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(
            system_instruction,
            user_input,
            tech_output,
            cmo_output,
            psych_output
        )
        
        # Call LLM for synthesis
        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for consistent logic
            )
            
            result_json = json.loads(response.choices[0].message.content)
            
            return ResolutionResult(
                winning_specialist=result_json.get('winning_specialist', 'UNKNOWN'),
                rationale=result_json.get('rationale', ''),
                cross_validation_flags=result_json.get('cross_validation_flags', []),
                overruled_points=result_json.get('overruled_points', []),
                final_plan=result_json.get('final_plan', ''),
                metadata=result_json.get('metadata', {})
            )
            
        except Exception as e:
            print(f"[ConflictResolver] Error during synthesis: {e}")
            # Return fallback result
            return ResolutionResult(
                winning_specialist="ERROR",
                rationale=f"Synthesis failed: {str(e)}",
                cross_validation_flags=[],
                overruled_points=[],
                final_plan="Unable to synthesize due to error.",
                metadata={"error": str(e)}
            )
    
    def _get_mode_instruction(self, mode: str) -> str:
        """Get hierarchical instruction based on mode."""
        if mode == "SPEED":
            return """
MODE: SPEED (MVP / Ship Fast)

PRIORITY: Low risk, high execution speed, minimize time-to-launch.

DECISION HIERARCHY:
- TECH_LEAD is the PRIMARY decision-maker
- CMO and PSYCHOLOGIST are advisory only
- Cut any feature that delays shipping
- Ignore grand visions and perfect UX if they slow down launch
- Accept technical debt if it speeds up delivery

RATIONALE: In SPEED mode, the biggest risk is NOT shipping. 
Technical feasibility trumps everything else.
"""
        
        elif mode == "GROWTH":
            return """
MODE: GROWTH (Market Domination)

PRIORITY: Maximum market impact, differentiation, revenue generation.

DECISION HIERARCHY:
- CMO is the DICTATOR
- TECH_LEAD must find a way to build what CMO needs
- PSYCHOLOGIST warnings about ethics are noted as "accepted risks"
- The goal is growth, not perfection or safety

RATIONALE: In GROWTH mode, the biggest risk is being boring.
Market opportunity trumps technical elegance and ethical purity.
"""
        
        elif mode == "SCALE":
            return """
MODE: SCALE (Enterprise Stability)

PRIORITY: Robustness, anti-fragility, ethics, long-term sustainability.

DECISION HIERARCHY:
- PSYCHOLOGIST + TECH_LEAD form a VETO ALLIANCE
- Any risky CMO strategy must be rejected
- Ethics and technical stability are non-negotiable
- The output must be boring, bulletproof, and enterprise-grade

RATIONALE: In SCALE mode, the biggest risk is reputational damage or systemic failure.
Stability and ethics trump growth opportunities.
"""
        
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be SPEED, GROWTH, or SCALE.")
    
    def _build_synthesis_prompt(self,
                                system_instruction: str,
                                user_input: str,
                                tech_output: str,
                                cmo_output: str,
                                psych_output: str) -> str:
        """Build the synthesis prompt for the LLM."""
        return f"""{system_instruction}

---

## INPUT DATA

**USER GOAL:**
{user_input}

**SPECIALIST OUTPUTS (ISOLATED):**

### [TECH_LEAD]
{tech_output}

### [CMO_STRATEGIST]
{cmo_output}

### [PSYCHOLOGIST]
{psych_output}

---

## YOUR TASK (THE CEO SYNTHESIS)

You are the CEO synthesizing isolated specialist opinions.

Perform the following cross-validation checks:

1. **FEASIBILITY CHECK:**
   - Does the CMO promise anything the TECH_LEAD said is impossible or very risky?
   - Does the PSYCHOLOGIST request features the TECH_LEAD flagged as infeasible?
   - Identify specific mismatches between CMO/PSYCH ambitions and TECH reality.

2. **ETHICS CHECK:**
   - Does the CMO or TECH_LEAD ignore ethical warnings from the PSYCHOLOGIST?
   - Are there dark patterns, manipulation tactics, or privacy violations proposed?
   - What is the ethical risk-reward trade-off?

3. **VALUE CHECK:**
   - Does the PSYCHOLOGIST suggest "perfect UX" features the CMO says won't generate revenue?
   - Are there user experience improvements that have no clear ROI?
   - What is the user value vs business value balance?

4. **WINNER SELECTION:**
   - Based on the MODE (SPEED/GROWTH/SCALE), which specialist's recommendation should dictate the final strategy?
   - What specific recommendations from other specialists are being overruled?

5. **FINAL PLAN:**
   - Synthesize an actionable, step-by-step plan
   - Be specific (no fluff like "research the market")
   - Include concrete next steps with rough timelines

---

## OUTPUT FORMAT (STRICT JSON)

Return ONLY valid JSON with this structure:

{{
    "winning_specialist": "TECH_LEAD" or "CMO" or "PSYCHOLOGIST",
    
    "rationale": "One paragraph explaining why this specialist won based on the MODE. Cite specific trade-offs.",
    
    "cross_validation_flags": [
        "EXAMPLE: CMO promised 'AI-powered matching in 2 weeks' but TECH_LEAD says this requires 6 months minimum",
        "EXAMPLE: PSYCHOLOGIST warns about dark pattern X but CMO says it's industry standard",
        "List all conflicts found during cross-validation"
    ],
    
    "overruled_points": [
        "Specific recommendations from non-winning specialists that were rejected and why"
    ],
    
    "final_plan": "Step-by-step action plan (be specific and concrete, 3-5 steps max)",
    
    "metadata": {{
        "estimated_cost": "$X or 'Unknown'",
        "estimated_timeline": "X weeks/months",
        "risk_level": "low/medium/high",
        "confidence": "0.0 to 1.0 (how confident are you in this synthesis?)"
    }}
}}

**CRITICAL:** Return ONLY the JSON object, nothing else.
"""


# Test function
def test_resolver():
    """Test the ConflictResolver with mock inputs."""
    resolver = ConflictResolver()
    
    # Mock outputs
    tech_output = """
    **Feasibility: RISKY**
    Building AI matching requires:
    - 6 months minimum for proper ML pipeline
    - $50k+ in training data and compute
    - Team of 3+ engineers
    
    **Technical Debt:**
    If we rush this in 2 weeks, we'll have a glorified keyword matcher, not real AI.
    """
    
    cmo_output = """
    **Market Opportunity: $50M TAM**
    The "AI-powered" angle is critical for Series A positioning.
    Competitors are launching in Q2, we MUST ship by end of Q1.
    
    **Growth Strategy:**
    - Launch with "AI-powered matching" as hero feature
    - Charge premium ($49/mo vs $29 for non-AI alternatives)
    """
    
    psych_output = """
    **UX Concern:**
    If the "AI matching" is actually just keyword matching, users will feel deceived.
    This creates ethical violation (false advertising) and bad UX (unmet expectations).
    
    **Recommendation:**
    Either build real AI (6 months) or don't claim AI (be honest about algorithm).
    """
    
    # Test SPEED mode
    result = resolver.resolve(
        user_input="Should we add AI-powered matching to our dating app for dentists?",
        tech_output=tech_output,
        cmo_output=cmo_output,
        psych_output=psych_output,
        mode="SPEED"
    )
    
    print("\n=== CONFLICT RESOLUTION RESULT (SPEED MODE) ===")
    print(json.dumps(result.to_dict(), indent=2))
    
    # Test GROWTH mode
    result_growth = resolver.resolve(
        user_input="Should we add AI-powered matching to our dating app for dentists?",
        tech_output=tech_output,
        cmo_output=cmo_output,
        psych_output=psych_output,
        mode="GROWTH"
    )
    
    print("\n=== CONFLICT RESOLUTION RESULT (GROWTH MODE) ===")
    print(json.dumps(result_growth.to_dict(), indent=2))


if __name__ == "__main__":
    test_resolver()
