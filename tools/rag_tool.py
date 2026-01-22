import os
import json
import vertexai
try:
    from vertexai import rag
except ImportError:
    print("[RAG] Warning: Could not import 'rag' from 'vertexai'. RAG features will be disabled.")
    rag = None
from vertexai.generative_models import GenerativeModel
from typing import Optional, Dict, Any, List

# Configuration
PROJECT_ID = "agenticraga"
LOCATION = "europe-west1"
DEFAULT_RAG_CORPUS_ID = "4611686018427387904"
# Models for RAG processing
FAST_MODEL_ID = "gemini-3-flash-001"
POWERFUL_MODEL_ID = "gemini-3-pro-preview" 
FALLBACK_MODEL_ID = "gemini-2.5-pro"  # User requested fallback (2.5 Pro)

# Initialize Vertex AI
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print("[RAG] Vertex AI Initialized")
except Exception as e:
    print(f"[RAG] Warning: Could not initialize Vertex AI: {e}")

# ... (Functions remove_celebrity_bias, classify_query_complexity, rewrite_query remain same, code below assumes they are preserved due to context matching or manual skip. 
# Wait, replace_file_content replaces the block. I need to be careful not to delete them if I targeted the top.)
# I will target ONLY the constants at the top first, then the synthesis block.

# CHANGE 1: Constants
# (Targeting via separate tool call implies sequentiality. I will do one large replace if possible or split.)
# I'll just do the whole file content update for the specific sections if I can, but replace_file_content requires contiguous block.
# I will make TWO replace calls. One for constants, one for synthesis removal.

# This tool call is for Constants.

try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print("[RAG] Vertex AI Initialized")
except Exception as e:
    print(f"[RAG] Warning: Could not initialize Vertex AI: {e}")

def remove_celebrity_bias(query: str) -> str:
    """
    Remove celebrity author names and branded frameworks from queries.
    This prevents the model from only searching for "famous" content.
    """
    banned_entities = [
        "Hormozi", "Alex Hormozi", "Cialdini", "Robert Cialdini",
        "Kiyosaki", "Robert Kiyosaki", "StoryBrand", "Donald Miller",
        "Seth Godin", "Gary Vee", "Grant Cardone", "Dan Kennedy",
        "Russell Brunson", "Eugene Schwartz", "SPIN Selling"
    ]
    
    cleaned = query
    for entity in banned_entities:
        # Case-insensitive replacement
        cleaned = cleaned.replace(entity, "")
        cleaned = cleaned.replace(entity.lower(), "")
    
    # Clean up extra spaces
    return " ".join(cleaned.split())

def classify_query_complexity(query: str, last_response: str = None, is_first_query: bool = False) -> str:
    """
    Context-Aware Query Router (v3.3).
    
    Rules:
    1. CHIT_CHAT: Greetings, meta-questions → Skip RAG.
    2. DEEP: First query OR short query after complex response.
    3. FOLLOW_UP: Simple continuation.
    """
    query_lower = query.lower().strip()
    
    # Rule 1: Chit-chat detection (fast, no LLM)
    chit_chat_patterns = ["hi", "hello", "thanks", "thank you", "bye", "who are you", "what can you do"]
    if any(query_lower.startswith(p) or query_lower == p for p in chit_chat_patterns):
        return "CHIT_CHAT"
    
    # Rule 2: First query always DEEP
    if is_first_query:
        return "DEEP"
    
    # Rule 3: Short follow-up after complex response → DEEP
    short_followups = ["why", "how", "explain", "what do you mean", "tell me more", "go on", "continue"]
    is_short_query = len(query.split()) <= 5
    if is_short_query and any(query_lower.startswith(f) for f in short_followups):
        if last_response and len(last_response) > 500:  # Last response was substantial
            print(f"[Router] Short query after complex response → DEEP")
            return "DEEP"
    
    # Default: FOLLOW_UP (single search)
    return "FOLLOW_UP"


# --- CONFIGURATION ANTI-OVERLOAD ---
MAX_FINAL_CHUNKS = 15  # Limite rígido: O LLM nunca receberá mais que 15 chunks de texto.
MIN_RELEVANCE_SCORE = 6  # Corte: Chunks com nota menor que 6/10 são descartados.

def rewrite_query(query: str, last_response: str = None, is_first_query: bool = False, agent_persona: str = None) -> List[str]:
    """
    [3x3 MATRIX v10 - DOMAIN ABSTRACTION & STRATEGIC DEPTH]
    Gera queries que separam o 'Conceito' do 'Produto'.
    """
    # 1. Check for Chit-Chat to save money
    if classify_query_complexity(query, last_response, is_first_query) == "CHIT_CHAT":
        return []

    # DEEP: 3x3 Matrix Expansion
    
    # Cascade Strategy
    model_cascade = [
        ("PRIMARY", POWERFUL_MODEL_ID),
        ("FALLBACK", FALLBACK_MODEL_ID),
        ("SAFE_ANCHOR", FAST_MODEL_ID)
    ]
    
    # Prepare Prompt
    persona_context = "Expert Analyst"
    if agent_persona:
        persona_context = agent_persona[:500] + "..." if len(agent_persona) > 500 else agent_persona
        
    prompt = f"""ROLE: You are an expert "Knowledge Strategist" acting as the {persona_context}.
INPUT: 
- User Query: "{query}"
- Agent Persona: "{persona_context}"

GOAL: Generate a 3x3 Search Matrix (9 queries) to retrieve the most relevant knowledge for THIS SPECIFIC AGENT to answer the query.

⚠️ CRITICAL INSTRUCTION: DOMAIN ABSTRACTION
The user is talking about a specific topic (e.g., "AI", "Crypto", "Coffee").
However, we need to solve this using UNIVERSAL FRAMEWORKS first.

=== LAYER 1: THE FRAMEWORK (Pure Strategy) ===
*Instruction:* STRIP AWAY the specific product/topic. Search ONLY for the strategic concepts relevant to the persona.
*Example:* If user asks "How to price my AI agent?", DO NOT search for "AI pricing". Search for "SaaS pricing psychology", "Value-based pricing models", "Blue Ocean Strategy".
*Goal:* Find the *theory* regardless of the industry.

=== LAYER 2: THE INTERSECTION (Applied Theory) ===
*Instruction:* Apply the framework to the general industry category.
*Example:* "Blue Ocean moves in software industry", "Network effects in digital products".
*Goal:* See how the theory applies to this *type* of business.

=== LAYER 3: THE CONTEXT (Specific Domain) ===
*Instruction:* Now you can use the specific keywords (e.g., "AI", "Machine Learning").
*Example:* "Monetization strategies for AI agents".
*Goal:* Specific tactical data.

CRITICAL RULES:
1. PIVOT: All 9 queries must be framed through the lens of "{persona_context}".
2. DEEP: Avoid superficial queries. Search for the *underlying concepts*.
3. NO NAMES: Do not include specific author names.

OUTPUT FORMAT (JSON ONLY):
{{
  "philosophical_queries": ["q1", "q2", "q3"],
  "strategic_queries": ["q1", "q2", "q3"],
  "tactical_queries": ["q1", "q2", "q3"]
}}"""
    
    # Execute Cascade
    response = None
    used_model = "NONE"
    
    for label, model_id in model_cascade:
        try:
            print(f"[RAG] Attempting Matrix Generation with {label} ({model_id})...")
            model = GenerativeModel(model_id)
            response = model.generate_content(prompt)
            if response and response.text:
                used_model = model_id
                break # Success
        except Exception as e:
            print(f"[RAG] Model {model_id} failed: {e}")
            continue # Try next

    if not response or not response.text:
        print("[RAG] All models failed. Falling back to simple query.")
        return [remove_celebrity_bias(query)]

    try:
        clean_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        matrix = json.loads(clean_json)

        all_queries = (
            matrix.get("philosophical_queries", []) +
            matrix.get("strategic_queries", []) +
            matrix.get("tactical_queries", [])
        )

        # Se NÃO tiver persona, removemos viés de celebridade.
        # Se TIVER persona, mantemos os nomes (ex: Taleb) para achar os livros certos.
        if not agent_persona:
            all_queries = [remove_celebrity_bias(q) for q in all_queries]

        print(f"[RAG] Matrix Generated via {used_model}: {len(all_queries)} queries (Persona Active: {bool(agent_persona)})")
        return all_queries[:9]

    except Exception as e:
        print(f"[RAG] JSON Parsing failed: {e}. Fallback to raw query.")
        return [query]

def filter_chunks(chunks: List[Dict], query: str) -> List[Dict]:
    """
    [SCORING FILTER v2.0 - ANTI-OVERLOAD + DEDUPLICATION + DIVERSITY]
    Classifica chunks de 0-10, remove duplicatas e garante diversidade.
    """
    if not chunks:
        return []

    # Filter model cascade: Try FAST, fallback to 2.5-flash
    filter_models = [
        ("FAST", FAST_MODEL_ID),
        ("FALLBACK_FLASH", "gemini-2.5-flash")
    ]

    # Prepara input numerado
    chunks_text = ""
    for i, c in enumerate(chunks):
        # Envia apenas os primeiros 300 chars para o avaliador (economia de tokens)
        chunks_text += f"--- CHUNK {i} ---\n{c['text'][:300]}...\n\n"

    prompt = f"""
TASK: Rate relevance to query: "{query}".
Scale: 0-10.
CRITERIA:
- 8-10: Contains a Framework, Definition, or Direct Solution.
- 5-7: Good context or related examples.
- 0-4: Generic noise or unrelated text.

INPUT:
{chunks_text}

OUTPUT FORMAT (JSON List):
[
  {{"index": 0, "score": 9}},
  {{"index": 1, "score": 3}}
]
"""

    # Try each model in cascade
    scored_chunks = []
    for label, model_id in filter_models:
        try:
            print(f"[RAG Filter] Attempting with {label} ({model_id})...")
            model = GenerativeModel(model_id)
            response = model.generate_content(prompt)
            clean_json = response.text.strip().replace("```json", "").replace("```", "").strip()
            scores = json.loads(clean_json)

            # Build scored chunks list
            for item in scores:
                idx = item.get("index")
                score = item.get("score", 0)

                if score >= MIN_RELEVANCE_SCORE and 0 <= idx < len(chunks):
                    chunk_data = chunks[idx].copy()
                    chunk_data['relevance_score'] = score
                    scored_chunks.append(chunk_data)

            print(f"[RAG Filter] ✅ Success with {label}. {len(scored_chunks)} chunks passed MIN_RELEVANCE_SCORE.")
            break  # Success, exit cascade

        except Exception as e:
            print(f"[RAG Filter] {label} failed: {e}")
            continue  # Try next model

    # If all models failed or no chunks passed
    if not scored_chunks:
        print("[RAG] Filter failed or too strict. Returning top 5 raw chunks.")
        return chunks[:5]

    # --- ADVANCED ORDERING & FILTERING ---
    
    # 1. DEDUPLICATION: Remove near-duplicate chunks
    def calculate_similarity(text1: str, text2: str) -> float:
        """Simple word overlap similarity (0-1)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    deduplicated = []
    for chunk in scored_chunks:
        is_duplicate = False
        for existing in deduplicated:
            similarity = calculate_similarity(chunk['text'], existing['text'])
            if similarity > 0.7:  # 70% overlap = duplicate
                is_duplicate = True
                # Keep the higher scored one
                if chunk['relevance_score'] > existing['relevance_score']:
                    deduplicated.remove(existing)
                    deduplicated.append(chunk)
                break
        if not is_duplicate:
            deduplicated.append(chunk)

    print(f"[RAG Filter] Deduplication: {len(scored_chunks)} → {len(deduplicated)} chunks")

    # 2. LENGTH NORMALIZATION: Penalize very short chunks
    for chunk in deduplicated:
        text_length = len(chunk['text'])
        if text_length < 100:  # Very short
            chunk['length_penalty'] = 0.5
        elif text_length < 300:  # Short
            chunk['length_penalty'] = 0.8
        else:  # Normal or long
            chunk['length_penalty'] = 1.0

    # 3. DIVERSITY SCORING: Ensure variety in final set
    # Sort by score first
    deduplicated.sort(key=lambda x: x['relevance_score'], reverse=True)

    # Select top chunks with diversity
    final_chunks = []
    for chunk in deduplicated:
        # Calculate diversity bonus (lower overlap with already selected = higher bonus)
        diversity_bonus = 1.0
        if final_chunks:
            avg_similarity = sum(
                calculate_similarity(chunk['text'], selected['text'])
                for selected in final_chunks
            ) / len(final_chunks)
            diversity_bonus = 1.0 - (avg_similarity * 0.3)  # Max 30% penalty for similarity

        # Calculate final composite score
        chunk['final_score'] = (
            chunk['relevance_score'] * 0.7 +  # Relevance is most important
            chunk['length_penalty'] * 2.0 +   # Length matters
            diversity_bonus * 1.0              # Diversity bonus
        )

        final_chunks.append(chunk)

        # Stop at MAX_FINAL_CHUNKS
        if len(final_chunks) >= MAX_FINAL_CHUNKS:
            break

    # 4. FINAL ORDERING: Sort by composite score
    final_chunks.sort(key=lambda x: x['final_score'], reverse=True)

    print(f"[RAG Filter] Final Selection: {len(final_chunks)} chunks (ordered by composite score)")
    
    # Return clean chunks (remove scoring metadata)
    return [{'text': c['text']} for c in final_chunks]

def rag_query(query: str, corpus_id: str = None, num_chunks: int = 10, metadata_filter: dict = None, agent_persona: str = None) -> dict:
    """
    [ORCHESTRATOR v10]
    Executa o pipeline e aplica o limite final de chunks.
    """
    print(f"\n--- Modular RAG Query: '{query}' ---")

    # 1. Rewrite (Domain Abstraction)
    search_queries = rewrite_query(query, agent_persona=agent_persona)

    # 2. Retrieval (Parallel)
    all_chunks = []
    seen_texts = set()

    selected_corpus_id = corpus_id if corpus_id else DEFAULT_RAG_CORPUS_ID
    corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{selected_corpus_id}"
    
    # Configure Retrieval
    rag_filter = None
    if metadata_filter:
        conditions = [f"{k} = '{v}'" for k, v in metadata_filter.items()]
        rag_filter = " AND ".join(conditions)

    retrieval_config = rag.RagRetrievalConfig(
        top_k=min(num_chunks, 10), # Limit retrieval per query
        filter=rag_filter
    )
    
    # Parallel Search Loop
    print(f"[RAG] Executing {len(search_queries)} parallel searches...")
    for q in search_queries:
        try:
            results = rag.retrieval_query(
                rag_resources=[rag.RagResource(rag_corpus=corpus_name)],
                text=q,
                rag_retrieval_config=retrieval_config,
            )
            if results and results.contexts:
                for result in results.contexts.contexts:
                    if result.text not in seen_texts:
                        seen_texts.add(result.text)
                        all_chunks.append({
                            "source": result.source_uri if result.source_uri else "Unknown Source",
                            "text": result.text
                        })
        except Exception as e:
            print(f"[RAG] Search failed for query '{q}': {e}")


    # 3. Filter (Anti-Overload)
    print(f"[RAG] Raw chunks retrieved: {len(all_chunks)}")
    filtered_chunks = filter_chunks(all_chunks, query)

    # 4. Final Cut (Hard Limit)
    final_chunks = filtered_chunks[:MAX_FINAL_CHUNKS]
    print(f"[RAG] Final chunks returned: {len(final_chunks)} (Max Limit: {MAX_FINAL_CHUNKS})")

    return {
        "direction": f"Context optimized for {agent_persona if agent_persona else 'General'}",
        "key_points": final_chunks
    }
