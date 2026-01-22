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
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                # Try GEMINI_API_KEY first, then fallback to GEMINIFLASH_API_KEY
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINIFLASH_API_KEY")
                if not api_key:
                    print("[Memory] Warning: No GEMINI_API_KEY or GEMINIFLASH_API_KEY found")
                    return None
                # Use embedding-001 for best quality (same model for storage & retrieval)
                # task_type will be specified per-call for optimal semantic matching
                self._embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/embedding-001",
                    google_api_key=api_key
                )
            except ImportError:
                print("[Memory] Warning: langchain_google_genai not installed")
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
            # Generate embedding with RETRIEVAL_DOCUMENT task_type for storage
            # This optimizes the vector for being retrieved later
            embedding = self.embeddings.embed_documents([content], task_type="RETRIEVAL_DOCUMENT")[0]
            
            # Insert into Supabase
            self.client.table("memory_vectors").insert({
                "conversation_id": conversation_id,
                "content": content,
                "fact_type": fact_type,
                "scope": scope,
                "agent_type": agent_type,
                "embedding": embedding
            }).execute()
            
            print(f"[Memory] Saved: [{scope}/{fact_type}] {content[:50]}...")
            return True
            
        except Exception as e:
            print(f"[Memory] Save failed: {e}")
            return False
    
    def save_memories_batch(
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
        Retrieve relevant facts using vector similarity search.
        
        Returns facts from AGENT and GLOBAL scopes only.
        CHAT facts should be retrieved separately (always included).
        """
        if not self.embeddings:
            print("[Memory] Cannot search: embeddings not available")
            return []
        
        try:
            # Generate query embedding with RETRIEVAL_QUERY task_type
            # This optimizes semantic bridge between query and stored documents
            query_embedding = self.embeddings.embed_query(query, task_type="RETRIEVAL_QUERY")
            
            # Call Supabase similarity search function
            response = self.client.rpc(
                "match_memory",
                {
                    "query_embedding": query_embedding,
                    "match_count": limit,
                    "filter_scope": ["AGENT", "GLOBAL"],
                    "filter_agent_type": agent_type
                }
            ).execute()
            
            results = []
            for row in response.data or []:
                results.append({
                    "content": row["content"],
                    "type": row["fact_type"],
                    "scope": row["scope"],
                    "created_at": row["created_at"],
                    "similarity": row.get("similarity", 0)
                })
            
            print(f"[Memory] Retrieved {len(results)} relevant facts")
            return results
            
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
