"""
Vector Memory Store (LangChain + Supabase pgvector)
====================================================
Implements 4-layer scoped context retrieval:
1. CHAT - Facts specific to this conversation (always injected)
2. AGENT - Facts specific to this agent type (vector search)
3. GLOBAL - Facts for all agents (vector search)
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
MEMORY_WINDOW = 15      # LLM remembers ~15 messages naturally
REFRESH_INTERVAL = 7    # Reinject context every 7 turns


class VectorMemoryStore:
    """
    Manages vector-based memory storage and retrieval.
    Uses Supabase pgvector for similarity search.
    """
    
    def __init__(self, supabase_client):
        self.client = supabase_client
        self._embeddings = None
    
    @property
    def embeddings(self):
        """Lazy load embeddings model."""
        if self._embeddings is None:
            try:
                from vertexai.language_models import TextEmbeddingModel
                # Using standard Gecko model for general embedding compatibility within Vertex AI
                self._embeddings = TextEmbeddingModel.from_pretrained("textembedding-gecko")
            except Exception as e:
                print(f"[Memory] Warning: Failed to load TextEmbeddingModel: {e}")
                self._embeddings = None
        return self._embeddings
    
    def save_memory(
        self,
        conversation_id: str,
        content: str,
        fact_type: str = "GENERAL",
        scope: str = "GLOBAL",
        agent_type: Optional[str] = None
    ) -> bool:
        """
        Save a fact to vector memory with embedding.
        
        Args:
            conversation_id: UUID of the conversation
            content: The fact content
            fact_type: PREFERENCE, CONSTRAINT, DECISION, GENERAL
            scope: CHAT, AGENT, GLOBAL
            agent_type: Type of agent (for AGENT scope)
        """
        if not self.embeddings:
            print("[Memory] Cannot save: embeddings not available")
            return False
        
        try:
            # Generate embedding using Vertex AI Model
            embedding_response = self.embeddings.get_embeddings([content])
            embedding = embedding_response[0].values
            
            # Insert into Supabase
            self.client.table("memory_vectors").insert({
                "conversation_id": conversation_id,
                "content": content,
                "fact_type": fact_type,
                "scope": scope,
                "agent_type": agent_type,
                "embedding": embedding
            }).execute()
            
            print(f"[Memory] Saved ({fact_type}/{scope}): {content[:50]}...")
            return True
            
        except Exception as e:
            print(f"[Memory] Save failed: {e}")
            return False
    
    def save_batch(
        self,
        conversation_id: str,
        facts: List[Dict],
        agent_type: Optional[str] = None
    ) -> int:
        """
        Save multiple facts in batch.
        
        Args:
            facts: List of dicts with keys: content, type, scope
        
        Returns:
            Number of facts saved
        """
        saved = 0
        for fact in facts:
            if self.save_memory(
                conversation_id=conversation_id,
                content=fact.get("content", ""),
                fact_type=fact.get("type", "GENERAL"),
                scope=fact.get("scope", "GLOBAL"),
                agent_type=agent_type if fact.get("scope") == "AGENT" else None
            ):
                saved += 1
        return saved
    
    def get_relevant_context(
        self,
        query: str,
        conversation_id: str,
        agent_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        [V6 RAG AUDIT FIX]
        Retrieve relevant facts using HYBRID SEARCH (Vector + BM25) with Reciprocal Rank Fusion (RRF).
        """
        if not self.embeddings:
            print("[Memory] Cannot search: embeddings not available")
            return []
        
        try:
            # 1. VECTOR SEARCH (Semantic) via Vertex AI
            embedding_response = self.embeddings.get_embeddings([query])
            query_embedding = embedding_response[0].values
            
            vector_response = self.client.rpc(
                "match_memory",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit * 2, # Busca o dobro para o RRF ter espaço
                    "filter_scope": ["AGENT", "GLOBAL"],
                    "filter_agent_type": agent_type
                }
            ).execute()
            
            vector_results = vector_response.data or []
            
            # 2. KEYWORD SEARCH (Fetch recent global/agent memories for BM25)
            # Como não temos RPC BM25 no Supabase, puxamos os 100 mais recentes para rankear localmente
            recent_query = self.client.table("memory_vectors")\
                .select("content, fact_type, scope, created_at")\
                .in_("scope", ["AGENT", "GLOBAL"])\
                .order("created_at", desc=True)\
                .limit(100)
            
            if agent_type:
                # O Supabase DB API requer chaining dinâmico para o OR não quebrar, mas vamos puxar tudo pro Agent e Global
                recent_query = self.client.table("memory_vectors")\
                    .select("content, fact_type, scope, created_at")\
                    .in_("scope", ["AGENT", "GLOBAL"])\
                    .order("created_at", desc=True)\
                    .limit(150)
                    
            recent_response = recent_query.execute()
            recent_results = recent_response.data or []
            
            # Executa BM25 Local (Sparse)
            bm25_results = []
            try:
                from rank_bm25 import BM25Okapi
                tokenized_corpus = [doc["content"].lower().split(" ") for doc in recent_results]
                if tokenized_corpus:
                    bm25 = BM25Okapi(tokenized_corpus)
                    tokenized_query = query.lower().split(" ")
                    doc_scores = bm25.get_scores(tokenized_query)
                    
                    # Associa scores e ordena
                    for idx, score in enumerate(doc_scores):
                        if score > 0:
                            item = recent_results[idx].copy()
                            item["bm25_score"] = score
                            bm25_results.append(item)
                    bm25_results.sort(key=lambda x: x["bm25_score"], reverse=True)
            except ImportError:
                print("[Memory] rank_bm25 ausente. Usando apenas Vetor.")
            
            # 3. RECIPROCAL RANK FUSION (RRF)
            k = 60 # Constante RRF
            fused_scores = {}
            fused_docs = {}
            
            # Adiciona Vector Ranks
            for rank, doc in enumerate(vector_results):
                content = doc["content"]
                if content not in fused_scores:
                    fused_scores[content] = 0
                    fused_docs[content] = doc
                fused_scores[content] += 1 / (rank + 1 + k)
                
            # Adiciona BM25 Ranks
            for rank, doc in enumerate(bm25_results):
                content = doc["content"]
                if content not in fused_scores:
                    fused_scores[content] = 0
                    fused_docs[content] = doc
                fused_scores[content] += 1 / (rank + 1 + k)
                
            # Ordena pelo RRF score final
            sorted_fused = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
            
            final_results = []
            for content, rrf_score in sorted_fused[:limit]:
                doc = fused_docs[content]
                final_results.append({
                    "content": doc["content"],
                    "type": doc.get("fact_type", doc.get("type", "GENERAL")),
                    "scope": doc["scope"],
                    "created_at": doc["created_at"],
                    "similarity": doc.get("similarity", 0), # Manter para log
                    "rrf_score": rrf_score
                })
            
            print(f"[Memory] Hybrid RRF Retrieved {len(final_results)} facts (Vector: {len(vector_results)}, BM25: {len(bm25_results)})")
            return final_results
            
        except Exception as e:
            print(f"[Memory] Retrieval failed: {e}")
            return []
    
    def get_chat_facts(
        self,
        conversation_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get ALL facts with CHAT scope for this conversation.
        These are always injected (never forgotten).
        """
        try:
            response = self.client.table("memory_vectors")\
                .select("content, fact_type, created_at")\
                .eq("conversation_id", conversation_id)\
                .eq("scope", "CHAT")\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            results = []
            for row in response.data or []:
                results.append({
                    "content": row["content"],
                    "type": row["fact_type"],
                    "created_at": row["created_at"]
                })
            
            return results
            
        except Exception as e:
            print(f"[Memory] Chat facts retrieval failed: {e}")
            return []
    
    def should_inject_context(
        self,
        turn_number: int,
        has_important_fact: bool = False
    ) -> bool:
        """
        Determine if context should be injected this turn.
        
        Args:
            turn_number: Current turn in conversation
            has_important_fact: True if PREFERENCE/CONSTRAINT detected
        """
        # Always on first turn
        if turn_number == 1:
            return True
        
        # Every REFRESH_INTERVAL turns
        if turn_number % REFRESH_INTERVAL == 0:
            return True
        
        # If important fact detected
        if has_important_fact:
            return True
        
        return False
    
    def format_facts_with_timestamps(
        self,
        facts: List[Dict]
    ) -> str:
        """
        Format facts with timestamps for conflict resolution.
        Most recent facts first.
        """
        # Sort by date (most recent first)
        sorted_facts = sorted(
            facts,
            key=lambda f: f.get("created_at", ""),
            reverse=True
        )
        
        lines = []
        for f in sorted_facts:
            date_str = ""
            if f.get("created_at"):
                # Extract just the date part
                date_str = f["created_at"][:10] if len(f["created_at"]) >= 10 else ""
                date_str = f"[{date_str}] "
            
            type_prefix = f"[{f.get('type', 'GENERAL')}] " if f.get('type') else ""
            lines.append(f"- {date_str}{type_prefix}{f['content']}")
        
        return "\n".join(lines)


# Singleton instance (initialized when db.py loads)
_memory_store: Optional[VectorMemoryStore] = None


def get_memory_store() -> Optional[VectorMemoryStore]:
    """Get the global memory store instance."""
    return _memory_store


def init_memory_store(supabase_client) -> VectorMemoryStore:
    """Initialize the global memory store."""
    global _memory_store
    _memory_store = VectorMemoryStore(supabase_client)
    print("[Memory] Vector Memory Store initialized")
    return _memory_store
