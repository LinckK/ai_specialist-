import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from dotenv import load_dotenv

# Try to import supabase, but handle if not installed
try:
    from supabase import create_client, Client
except ImportError:
    Client = Any
    create_client = None

from .models import Message, Conversation

load_dotenv()

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.url: str = os.environ.get("SUPABASE_URL")
        self.key: str = os.environ.get("SUPABASE_KEY")
        self.client: Optional[Client] = None
        
        if self.url and self.key and create_client:
            try:
                self.client = create_client(self.url, self.key)
                print("[DB] Supabase client initialized.")
                
                # Initialize vector memory store
                try:
                    from .memory_store import init_memory_store
                    init_memory_store(self.client)
                except ImportError as e:
                    print(f"[DB] Memory store not available: {e}")
            except Exception as e:
                print(f"[DB] Failed to initialize Supabase client: {e}")
        else:
            print("[DB] Supabase credentials missing or library not installed. Running in memory-only mode (NOT PERSISTENT).")
            
        self._initialized = True
        self.agents_memory = {}
        self.conversation_facts_memory = {}

    def create_conversation(self, user_id: Optional[UUID] = None, title: str = "New Conversation") -> Conversation:
        """Creates a new conversation in the database."""
        conv_id = uuid4()
        now = datetime.now().isoformat()
        
        conversation_data = {
            "id": str(conv_id),
            "user_id": str(user_id) if user_id else None,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "metadata": {}
        }

        if self.client:
            try:
                self.client.table("conversations").insert(conversation_data).execute()
                print(f"[DB] Conversation {conv_id} created successfully in Supabase.")
            except Exception as e:
                print(f"[DB] Error creating conversation: {e}")
                import traceback
                traceback.print_exc()
                # CRITICAL: Do not return a valid object if DB failed, or history won't save.
                raise Exception(f"Failed to create conversation in DB: {e}")
        
        return Conversation(**conversation_data)

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Retrieves a conversation by ID."""
        if not self.client:
            return None
            
        try:
            response = self.client.table("conversations").select("*").eq("id", conversation_id).execute()
            if response.data:
                return Conversation(**response.data[0])
        except Exception as e:
            print(f"[DB] Error fetching conversation: {e}")
        return None

    def add_message(self, message: Message) -> bool:
        """Adds a message to the database."""
        msg_data = message.model_dump(mode='json')
        
        # Ensure UUIDs are strings
        msg_data['id'] = str(msg_data['id'])
        msg_data['conversation_id'] = str(msg_data['conversation_id'])
        
        if self.client:
            try:
                self.client.table("messages").insert(msg_data).execute()
                # Debug: Confirm save
                content_preview = msg_data.get('content', '')[:50] if msg_data.get('content') else 'NO CONTENT'
                print(f"[DB] Saved message ({msg_data['role']}): {content_preview}...")
                return True
            except Exception as e:
                print(f"[DB] Error adding message: {e}")
                import traceback
                traceback.print_exc()
                return False
        return True # Return true in memory mode to not break flow

    def list_conversations(self, limit: int = 100) -> List[Conversation]:
        """Lists recent conversations."""
        if not self.client:
            return []
            
        try:
            response = self.client.table("conversations")\
                .select("*")\
                .order("updated_at", desc=True)\
                .limit(limit)\
                .execute()
            
            conversations = []
            for conv_data in response.data:
                conversations.append(Conversation(**conv_data))
            return conversations
        except Exception as e:
            print(f"[DB] Error listing conversations: {e}")
            return []

    def get_history(self, conversation_id: str, limit: int = 50) -> List[Message]:
        """Retrieves message history for a conversation."""
        if not self.client:
            return []

        try:
            response = self.client.table("messages")\
                .select("*")\
                .eq("conversation_id", conversation_id)\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            
            messages = []
            for msg_data in response.data:
                messages.append(Message(**msg_data))
            
            # CRITICAL FIX: We fetched DESC (newest first) for LIMIT,
            # but we need chronological order (oldest first) for conversation flow
            messages.reverse()
            return messages
        except Exception as e:
            print(f"[DB] Error fetching history: {e}")
            return []

    def update_conversation_timestamp(self, conversation_id: str):
        """Updates the updated_at timestamp of a conversation."""
        if self.client:
            try:
                now = datetime.now().isoformat()
                self.client.table("conversations").update({"updated_at": now}).eq("id", conversation_id).execute()
            except Exception as e:
                print(f"[DB] Error updating conversation timestamp: {e}")

    def delete_conversation(self, conversation_id: str) -> bool:
        """Deletes a conversation and all its messages."""
        if not self.client:
            print("[DB] Cannot delete - no database connection")
            return False
        
        try:
            # Delete all messages first (foreign key constraint)
            self.client.table("messages").delete().eq("conversation_id", conversation_id).execute()
            print(f"[DB] Deleted messages for conversation {conversation_id}")
            
            # Delete the conversation
            self.client.table("conversations").delete().eq("id", conversation_id).execute()
            print(f"[DB] Deleted conversation {conversation_id}")
            return True
        except Exception as e:
            print(f"[DB] Error deleting conversation: {e}")
            return False

    # --- Agent Registry Operations ---

    def get_agent(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves an agent configuration by name."""
        if not self.client:
            # Fallback to memory
            return self.agents_memory.get(agent_name)
        
        try:
            response = self.client.table("agents").select("*").eq("name", agent_name).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"[DB] Error fetching agent '{agent_name}': {e}")
        return None

    def list_agents(self) -> List[Dict[str, Any]]:
        """Lists all enabled agents."""
        if not self.client:
            # Fallback to memory
            return list(self.agents_memory.values())
        
        try:
            response = self.client.table("agents").select("*").eq("enabled", True).execute()
            return response.data
        except Exception as e:
            print(f"[DB] Error listing agents: {e}")
            return []

    def create_agent(self, name: str, description: str, config: Dict[str, Any]) -> bool:
        """Creates or updates an agent profile with automatic corpus creation."""
        
        # In-memory fallback logic
        if not self.client:
            print(f"[DB] (Memory Mode) Creating agent '{name}'")
            self.agents_memory[name] = {
                "name": name,
                "description": description,
                "config": config,
                "enabled": True,
                "updated_at": datetime.now().isoformat()
            }
            return True
        
        # Import corpus manager
        from .tools.corpus_manager import create_corpus
        
        # Check if agent already exists
        existing = self.client.table("agents").select("*").eq("name", name).execute()
        is_update = len(existing.data) > 0
        
        # If creating new agent, create a dedicated corpus
        if not is_update:
            # Check if corpus_id is explicitly provided (Shared Memory / Sub-Agent)
            provided_corpus_id = config.get('rag_config', {}).get('corpus_id')
            
            if provided_corpus_id:
                print(f"[DB] 🔗 Linking new agent '{name}' to EXISTING corpus {provided_corpus_id}")
                # No need to create specific corpus, just use the provided one
            else:
                # Create NEW dedicated corpus
                corpus_id = create_corpus(
                    display_name=f"{name}_corpus",
                    description=f"Knowledge base for {name} agent - {description}"
                )
                
                if corpus_id:
                    print(f"[DB] ✅ Created dedicated corpus {corpus_id} for agent '{name}'")
                    # Ensure rag_config exists in config
                    if 'rag_config' not in config:
                        config['rag_config'] = {}
                    config['rag_config']['corpus_id'] = corpus_id
                else:
                    print(f"[DB] ⚠️  Warning: Failed to create corpus for agent '{name}'")
        
        data = {
            "name": name,
            "description": description,
            "config": config,
            "enabled": True,
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            # Upsert based on name
            self.client.table("agents").upsert(data, on_conflict="name").execute()
            return True
        except Exception as e:
            print(f"[DB] Error creating/updating agent '{name}': {e}")
            return False

    def update_agent_config(self, name: str, config: Dict[str, Any]) -> bool:
        """Updates just the config field of an agent."""
        if not self.client:
             if name in self.agents_memory:
                 self.agents_memory[name]['config'] = config
                 return True
             return False
             
        try:
            self.client.table("agents").update({"config": config}).eq("name", name).execute()
            return True
        except Exception as e:
             print(f"[DB] Error updating config for '{name}': {e}")
             return False

    def delete_agent(self, agent_name: str) -> bool:
        """Deletes an agent and its associated corpus."""
        if not self.client:
            if agent_name in self.agents_memory:
                del self.agents_memory[agent_name]
                print(f"[DB] (Memory Mode) Deleted agent '{agent_name}'")
                return True
            return False
        
        # Import corpus manager
        from .tools.corpus_manager import delete_corpus
        
        try:
            # Get agent's corpus_id before deleting
            agent_data = self.client.table("agents").select("*").eq("name", agent_name).execute()
            
            if agent_data.data:
                config = agent_data.data[0].get('config', {})
                if isinstance(config, str):
                    import json
                    config = json.loads(config)
                
                rag_config = config.get('rag_config', {})
                corpus_id = rag_config.get('corpus_id')
                
                if corpus_id:
                    print(f"[DB] 🗑️  Deleting corpus {corpus_id} for agent '{agent_name}'...")
                    delete_corpus(corpus_id)
            
            # Delete the agent from database
            self.client.table("agents").delete().eq("name", agent_name).execute()
            print(f"[DB] ✅ Deleted agent '{agent_name}' and its corpus")
            return True
        except Exception as e:
            print(f"[DB] Error deleting agent '{agent_name}': {e}")
            return False

    # --- Persistent Memory Operations (v5.1) ---

    def save_facts(self, conversation_id: str, new_facts: List) -> bool:
        """
        Saves new facts to the persistent memory.
        Accepts either:
        - List of strings (legacy): ["fact1", "fact2"]
        - List of dicts (v6.0): [{"content": "...", "type": "PREFERENCE"}, ...]
        """
        if not new_facts:
            return True

        if not self.client:
            # Memory fallback
            if conversation_id not in self.conversation_facts_memory:
                 self.conversation_facts_memory[conversation_id] = []
            self.conversation_facts_memory[conversation_id].extend(new_facts)
            print(f"[DB] (Memory Mode) Saved {len(new_facts)} facts for {conversation_id}")
            return True
            
        try:
            rows = []
            for fact in new_facts:
                if isinstance(fact, dict):
                    # New format: {"content": "...", "type": "PREFERENCE"}
                    rows.append({
                        "conversation_id": conversation_id, 
                        "fact_content": fact.get("content", str(fact)),
                        "fact_type": fact.get("type", "GENERAL")
                    })
                else:
                    # Legacy format: plain string
                    rows.append({
                        "conversation_id": conversation_id, 
                        "fact_content": str(fact),
                        "fact_type": "GENERAL"
                    })
            
            self.client.table("agent_facts").insert(rows).execute()
            print(f"[DB] Saved {len(new_facts)} facts to DB for conversation {conversation_id}")
            return True
        except Exception as e:
            print(f"[DB] Error saving facts: {e}")
            return False

    def get_facts(self, conversation_id: str, limit: int = 100) -> List[dict]:
        """
        Retrieves persistent facts for a conversation.
        Returns list of dicts: [{"content": "...", "type": "PREFERENCE"}, ...]
        """
        if not self.client:
             # Memory fallback
            return self.conversation_facts_memory.get(conversation_id, [])

        try:
            response = self.client.table("agent_facts")\
                .select("fact_content, fact_type, created_at")\
                .eq("conversation_id", conversation_id)\
                .order("created_at", desc=False)\
                .limit(limit)\
                .execute()
            
            facts = [{"content": row['fact_content'], "type": row.get('fact_type', 'GENERAL')} 
                     for row in response.data]
            return facts
        except Exception as e:
            print(f"[DB] Error fetching facts: {e}")
            return []

    def get_critical_facts(self, conversation_id: str, limit: int = 50) -> List[dict]:
        """
        Retrieves CRITICAL facts (PREFERENCE, CONSTRAINT) - these should NEVER be forgotten.
        """
        if not self.client:
            # Memory fallback - filter by type
            all_facts = self.conversation_facts_memory.get(conversation_id, [])
            return [f for f in all_facts if isinstance(f, dict) and f.get("type") in ["PREFERENCE", "CONSTRAINT"]]

        try:
            response = self.client.table("agent_facts")\
                .select("fact_content, fact_type")\
                .eq("conversation_id", conversation_id)\
                .in_("fact_type", ["PREFERENCE", "CONSTRAINT"])\
                .order("created_at", desc=False)\
                .limit(limit)\
                .execute()
            
            facts = [{"content": row['fact_content'], "type": row['fact_type']} 
                     for row in response.data]
            return facts
        except Exception as e:
            print(f"[DB] Error fetching critical facts: {e}")
            return []

# Global instance
db = Database()


