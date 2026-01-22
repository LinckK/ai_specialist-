"""
Conflict resolution tool for analyzing and resolving contradictions
between multiple RAG results from different sources.
"""

import json
from typing import List, Dict, Any, Optional
import litellm
import os

def resolve_conflicts(rag_results: List[Dict[str, Any]], query: str = None) -> str:
    """
    Analyzes multiple RAG results and resolves conflicts between them.
    
    Args:
        rag_results: List of RAG result dictionaries, each containing:
            - 'direction': Main summary/answer
            - 'key_points': List of key points with 'source' and 'text'
        query: Original query (optional, for context)
        
    Returns:
        Resolved synthesis with conflict notes
    """
    if not rag_results:
        return "Error: No RAG results provided for conflict resolution"
    
    if len(rag_results) == 1:
        return "Only one source provided, no conflicts to resolve."
    
    # Prepare conflict analysis prompt
    sources_text = ""
    for i, result in enumerate(rag_results):
        direction = result.get("direction", "N/A")
        key_points = result.get("key_points", [])
        sources = [kp.get("source", "Unknown") for kp in key_points]
        unique_sources = list(set(sources))
        
        sources_text += f"\n--- Source {i+1} ---\n"
        sources_text += f"Direction: {direction}\n"
        sources_text += f"Sources: {', '.join(unique_sources)}\n"
        sources_text += f"Key Points:\n"
        for kp in key_points:
            sources_text += f"  - {kp.get('text', '')[:200]}...\n"
    
    conflict_prompt = f"""Analyze the following information from multiple sources and identify any conflicts, contradictions, or inconsistencies.

{sources_text}

Original Query: {query if query else "Not provided"}

Please:
1. Identify any conflicts or contradictions between the sources
2. Determine which source(s) are more credible based on:
   - Source metadata (book title, author, date)
   - Context relevance to the query
   - Consistency with other sources
   - Recency (if applicable)
3. Provide a resolved synthesis that:
   - Integrates the most credible information
   - Notes any conflicts that couldn't be fully resolved
   - Explains the reasoning for source selection

Format your response as JSON with:
- "conflicts": List of identified conflicts
- "credible_sources": List of most credible sources with reasoning
- "resolved_synthesis": The final integrated answer
- "notes": Any additional notes about the resolution process
"""

    try:
        # Use a model for conflict resolution (can be configured)
        model = os.getenv("CONFLICT_RESOLUTION_MODEL", "gemini/gemini-2.5-flash-lite")
        
        response = litellm.completion(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing information from multiple sources, identifying conflicts, and synthesizing credible information."
                },
                {
                    "role": "user",
                    "content": conflict_prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more consistent analysis
            api_key=os.getenv("GEMINIFLASH_API_KEY")
        )
        
        response_text = response.choices[0].message.content
        
        # Try to parse as JSON, fallback to plain text
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(response_text)
            
            # Format the result
            result = "=== CONFLICT RESOLUTION ===\n\n"
            
            if "conflicts" in parsed:
                result += "Identified Conflicts:\n"
                for conflict in parsed["conflicts"]:
                    result += f"  - {conflict}\n"
                result += "\n"
            
            if "credible_sources" in parsed:
                result += "Credible Sources:\n"
                for source in parsed["credible_sources"]:
                    if isinstance(source, dict):
                        result += f"  - {source.get('source', 'Unknown')}: {source.get('reasoning', '')}\n"
                    else:
                        result += f"  - {source}\n"
                result += "\n"
            
            if "resolved_synthesis" in parsed:
                result += "Resolved Synthesis:\n"
                result += f"{parsed['resolved_synthesis']}\n\n"
            
            if "notes" in parsed:
                result += f"Notes: {parsed['notes']}\n"
            
            return result
        
        except json.JSONDecodeError:
            # If not JSON, return the raw response
            return f"=== CONFLICT RESOLUTION ===\n\n{response_text}"
    
    except Exception as e:
        return f"Error during conflict resolution: {e}"

def conflict_resolver(rag_results: List[Dict[str, Any]], query: str = None) -> str:
    """
    Main conflict resolver function (alias for resolve_conflicts).
    """
    return resolve_conflicts(rag_results, query)

