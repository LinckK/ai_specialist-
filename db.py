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

from pathlib import Path
 # Explicitly load .env from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

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

    # ================================================================
    # V2: PROJECT STATE & BOARDROOM METHODS
    # These are ADDITIVE — they don't change any existing behavior.
    # ================================================================

    def create_project(self, name: str, user_id: str = None, drive_folder_id: str = None) -> Optional[Dict]:
        """Creates a new project with an empty context_snapshot."""
        data = {
            "name": name,
            "status": "active",
            "context_snapshot": {},
        }
        if user_id:
            data["user_id"] = user_id
        if drive_folder_id:
            data["drive_folder_id"] = drive_folder_id

        if not self.client:
            # Local fallback
            fake_id = str(uuid4())
            data["id"] = fake_id
            if not hasattr(self, '_local_projects'):
                self._local_projects = {}
            self._local_projects[fake_id] = data
            print(f"[DB] Project '{name}' created locally (ID: {fake_id[:8]}...)")
            return data

        try:
            response = self.client.table("projects").insert(data).execute()
            if response.data:
                print(f"[DB] Project '{name}' created (ID: {response.data[0]['id'][:8]}...)")
                return response.data[0]
        except Exception as e:
            print(f"[DB] Error creating project: {e}")
        return None

    def get_project(self, project_id: str) -> Optional[Dict]:
        """Fetches a project by ID, including its context_snapshot."""
        if not self.client:
            return getattr(self, '_local_projects', {}).get(project_id)

        try:
            response = self.client.table("projects")\
                .select("*")\
                .eq("id", project_id)\
                .single()\
                .execute()
            return response.data
        except Exception as e:
            print(f"[DB] Error fetching project: {e}")
            return None

    def list_projects(self, user_id: str = None, status: str = "active") -> List[Dict]:
        """Lists projects, optionally filtered by user and status."""
        if not self.client:
            projects = list(getattr(self, '_local_projects', {}).values())
            if status:
                projects = [p for p in projects if p.get("status") == status]
            return projects

        try:
            query = self.client.table("projects").select("id, name, status, context_snapshot, created_at, updated_at")
            if user_id:
                query = query.eq("user_id", user_id)
            if status:
                query = query.eq("status", status)
            response = query.order("updated_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            print(f"[DB] Error listing projects: {e}")
            return []

    def update_context(self, project_id: str, patch: Dict) -> Optional[Dict]:
        """
        Applies a deep_merge patch to a project's context_snapshot.
        Only updates keys present in the patch; preserves everything else.
        """
        project = self.get_project(project_id)
        if not project:
            print(f"[DB] Project {project_id} not found.")
            return None

        current = project.get("context_snapshot", {})
        merged = _deep_merge(current, patch)

        if not self.client:
            self._local_projects[project_id]["context_snapshot"] = merged
            return merged

        try:
            response = self.client.table("projects")\
                .update({"context_snapshot": merged})\
                .eq("id", project_id)\
                .execute()
            if response.data:
                return response.data[0].get("context_snapshot", merged)
        except Exception as e:
            print(f"[DB] Error updating context: {e}")
        return merged

    def save_lesson(self, content: str, lesson_type: str = "fact",
                    project_id: str = None, source: str = "system", tags: List[str] = None) -> bool:
        """
        Saves a lesson to episodic_memory.
        Types: preference | fact | feedback | mistake | success
        """
        data = {
            "content": content,
            "type": lesson_type,
            "source": source,
            "tags": tags or [],
        }
        if project_id:
            data["project_id"] = project_id

        if not self.client:
            if not hasattr(self, '_local_memories'):
                self._local_memories = []
            data["id"] = str(uuid4())
            self._local_memories.append(data)
            print(f"[DB] Lesson saved locally: '{content[:40]}...'")
            return True

        try:
            self.client.table("episodic_memory").insert(data).execute()
            print(f"[DB] Lesson saved: '{content[:40]}...'")
            return True
        except Exception as e:
            print(f"[DB] Error saving lesson: {e}")
            return False

    def recall_lessons(self, query: str, project_id: str = None,
                       lesson_type: str = None, limit: int = 5) -> List[Dict]:
        """
        Recalls lessons from episodic_memory by keyword search.
        Phase 3 will upgrade this to vector similarity search.
        """
        if not self.client:
            # Local keyword search
            memories = getattr(self, '_local_memories', [])
            query_lower = query.lower()
            results = []
            for mem in memories:
                if project_id and mem.get("project_id") != project_id:
                    continue
                if lesson_type and mem.get("type") != lesson_type:
                    continue
                words = query_lower.split()
                hits = sum(1 for w in words if w in mem.get("content", "").lower())
                if hits > 0:
                    results.append((hits, mem))
            results.sort(key=lambda x: x[0], reverse=True)
            return [m for _, m in results[:limit]]

        try:
            query_builder = self.client.table("episodic_memory")\
                .select("id, content, type, source, tags, created_at")\
                .ilike("content", f"%{query}%")
            if project_id:
                query_builder = query_builder.eq("project_id", project_id)
            if lesson_type:
                query_builder = query_builder.eq("type", lesson_type)
            response = query_builder\
                .order("created_at", desc=True)\
                .limit(limit)\
                .execute()
            return response.data or []
        except Exception as e:
            print(f"[DB] Error recalling lessons: {e}")
            return []

    def create_run(self, project_id: str, trigger_source: str = "cli",
                   trigger_input: str = None, agents_used: List[str] = None) -> Optional[str]:
        """
        Creates an execution_run record. Returns the run ID.
        """
        data = {
            "project_id": project_id,
            "trigger_source": trigger_source,
            "status": "processing",
            "agents_used": agents_used or [],
        }
        if trigger_input:
            data["trigger_input"] = trigger_input

        if not self.client:
            run_id = str(uuid4())
            data["id"] = run_id
            if not hasattr(self, '_local_runs'):
                self._local_runs = {}
            self._local_runs[run_id] = data
            return run_id

        try:
            response = self.client.table("execution_runs").insert(data).execute()
            if response.data:
                return response.data[0]["id"]
        except Exception as e:
            print(f"[DB] Error creating run: {e}")
        return None

    def update_run(self, run_id: str, status: str = None, agent_outputs: list = None,
                   final_plan: dict = None, state_patch: dict = None,
                   user_feedback: str = None, feedback_sentiment: str = None) -> bool:
        """Updates an execution_run with results."""
        updates = {}
        if status:
            updates["status"] = status
        if agent_outputs is not None:
            updates["agent_outputs"] = agent_outputs
        if final_plan is not None:
            updates["final_plan"] = final_plan
        if state_patch is not None:
            updates["state_patch"] = state_patch
        if user_feedback:
            updates["user_feedback"] = user_feedback
        if feedback_sentiment:
            updates["feedback_sentiment"] = feedback_sentiment
        if status in ("completed", "failed", "rejected"):
            updates["completed_at"] = datetime.now().isoformat()

        if not updates:
            return True

        if not self.client:
            if hasattr(self, '_local_runs') and run_id in self._local_runs:
                self._local_runs[run_id].update(updates)
            return True

        try:
            self.client.table("execution_runs").update(updates).eq("id", run_id).execute()
            return True
        except Exception as e:
            print(f"[DB] Error updating run: {e}")
            return False


def _deep_merge(base: dict, patch: dict) -> dict:
    """
    Recursively merges 'patch' into 'base'.
    - Scalar values in patch overwrite base.
    - Dicts are merged recursively.
    - Base keys not in patch are preserved.
    """
    result = base.copy()
    for key, value in patch.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# Global instance
db = Database()


