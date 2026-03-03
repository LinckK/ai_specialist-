import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

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
LOCATION = "us-west1"
DEFAULT_RAG_CORPUS_ID = "4611686018427387904"
# Models for RAG processing
FAST_MODEL_ID = "gemini-2.5-flash"
POWERFUL_MODEL_ID = "gemini-2.5-pro" 
FALLBACK_MODEL_ID = "gemini-2.5-pro"

# Initialize Vertex AI
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
    [V4 RAG PIPELINE FIX]
    Simplified Query Expansion for speed and precision.
    Instead of 3 LLM calls for a 3x3 Matrix, we use a single fast call for synonym/context expansion,
    plus the raw exact query (crucial for Legal/BM25).
    """
    # 1. Check for Chit-Chat to save money
    if classify_query_complexity(query, last_response, is_first_query) == "CHIT_CHAT":
        return []

    queries = [query] # ALWAYS include the exact raw query first (for exact matches)

    persona_context = "Expert"
    if agent_persona:
        persona_context = agent_persona[:200]
        
    prompt = f"""You are a '{persona_context}'. 
The user asked: "{query}"
Provide exactly TWO alternate search queries to retrieve relevant documents.
1. A broader conceptual variation.
2. A specific tactical variation (synonyms).
Do not explain. Just output the two queries separated by a newline."""

    try:
        model = GenerativeModel(FAST_MODEL_ID)
        response = model.generate_content(prompt)
        if response and response.text:
            expansions = [line.strip() for line in response.text.split('\n') if line.strip() and len(line) > 5]
            queries.extend(expansions[:2])
    except Exception as e:
         print(f"[RAG] Fast expansion failed: {e}. Using raw query only.")

    # Apply anti-bias
    if not agent_persona:
        queries = [remove_celebrity_bias(q) for q in queries]
        
    print(f"[RAG] Fast Expansion generated {len(queries)} queries.")
    return list(set(queries)) # Deduplicate

def filter_chunks(chunks: List[Dict], query: str) -> List[Dict]:
    """
    [V2 RAG PIPELINE FIX]
    Substitui a cara avaliação do Gemini (Scoring Filter V2.0)
    pelo classificador Cross-Encoder (Cohere Rerank) ou dedup via Similaridade Semântica leve.
    """
    if not chunks:
        return []

    # 1. Deduplicação Antecipada (Evitar token desperdiçado no Re-Ranker)
    def calculate_similarity(text1: str, text2: str) -> float:
         words1 = set(text1.lower().split())
         words2 = set(text2.lower().split())
         if not words1 or not words2:
              return 0.0
         return len(words1 & words2) / len(words1 | words2)

    deduped_chunks = []
    seen_texts = set()
    for chunk in chunks:
        if len(chunk['text']) < 150: # Remove lixos muito pequenos
            continue
        
        is_duplicate = False
        for ex in deduped_chunks:
             if calculate_similarity(chunk['text'], ex['text']) > 0.7:
                 is_duplicate = True
                 break
        if not is_duplicate:
            deduped_chunks.append(chunk)

    print(f"[RAG Filter] Raw: {len(chunks)} | Deduped: {len(deduped_chunks)}")

    # FALLBACK SE NÃO TIVER CHAVE (Devolve os mais relevantes baseados na dedup e Top_K do Vector Search)
    final_chunks = deduped_chunks[:MAX_FINAL_CHUNKS]
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

    # Anti-Loop Guarantee (if RAG finds nothing, tell the LLM explicitly instead of returning an empty array)
    if not final_chunks:
        return {
             "direction": f"Context optimized for {agent_persona if agent_persona else 'General'}",
             "key_points": ["CRITICAL: THE KNOWLEDGE BASE/RAG DOES NOT CONTAIN ANY INFORMATION RELEVANT TO THIS QUERY. DO NOT TRY TO REPHRASE OR SEARCH AGAIN IN THIS TURN. RELY ON USER INPUT OR GENERAL KNOWLEDGE."]
        }

    return {
        "direction": f"Context optimized for {agent_persona if agent_persona else 'General'}",
        "key_points": final_chunks
    }
