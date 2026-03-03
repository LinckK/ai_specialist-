from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from .config import AgentConfig, ModelConfig, RAGConfig
from .db import db
from .tools.corpus_manager import create_corpus, delete_corpus

@dataclass
class AgentProfile:
    name: str
    description: str
    config: AgentConfig
    enabled: bool = True

class AgentRegistry:
    def __init__(self):
        pass # No local state needed anymore

    def register_agent(self, profile: AgentProfile) -> bool:
        """Registers a new agent profile in the database and creates a dedicated RAG corpus."""
        
        # Create dedicated corpus for this agent (unless it already has one)
        if not profile.config.rag_config.corpus_id:
            print(f"[Registry] Creating dedicated corpus for agent '{profile.name}'...")
            corpus_id = create_corpus(
                display_name=f"{profile.name}_corpus",
                description=f"Knowledge base for {profile.name} agent"
            )
            
            if corpus_id:
                profile.config.rag_config.corpus_id = corpus_id
                profile.config.rag_config.corpus_name = f"{profile.name}_corpus"
                print(f"[Registry] ✅ Corpus created: {corpus_id}")
            else:
                print(f"[Registry] ⚠️  Warning: Failed to create corpus for '{profile.name}'")
                # Continue anyway - agent can still work without RAG
        
        # Convert config to dict
        config_dict = {
            "model_config": {
                "litellm_model_name": profile.config.model_config.litellm_model_name,
                "temperature": profile.config.model_config.temperature,
                "max_tokens": profile.config.model_config.max_tokens
            },
            "rag_config": {
                "corpus_id": profile.config.rag_config.corpus_id,
                "corpus_name": profile.config.rag_config.corpus_name
            },
            "base_system_prompt": profile.config.base_system_prompt,
            "specialized_system_prompt": profile.config.specialized_system_prompt
        }
        return db.create_agent(profile.name, profile.description, config_dict)

    def get_agent(self, name: str) -> Optional[AgentProfile]:
        """Retrieves an agent profile by name from the database."""
        agent_data = db.get_agent(name)
        if not agent_data:
            return None
            
        # Reconstruct AgentConfig from JSON
        config_data = agent_data["config"]
        
        # Handle case where config is returned as a JSON string
        if isinstance(config_data, str):
            try:
                import json
                config_data = json.loads(config_data)
            except json.JSONDecodeError:
                print(f"Error parsing config for agent {name}: Invalid JSON")
                config_data = {}
        
        # Handle potential missing keys gracefully or with defaults
        model_conf = ModelConfig.from_dict(config_data.get("model_config", {}))
        rag_conf = RAGConfig.from_dict(config_data.get("rag_config", {}))
        
        config = AgentConfig(
            model_config=model_conf,
            rag_config=rag_conf,
            base_system_prompt=config_data.get("base_system_prompt", ""),
            specialized_system_prompt=config_data.get("specialized_system_prompt", "")
        )
        
        return AgentProfile(
            name=agent_data["name"],
            description=agent_data["description"],
            config=config,
            enabled=agent_data["enabled"]
        )

    def list_agents(self) -> List[AgentProfile]:
        """Lists all available agent profiles from the database."""
        agents_data = db.list_agents()
        profiles = []
        
        for agent_data in agents_data:
            # Reconstruct AgentConfig
            config_data = agent_data["config"]
            
            # Handle case where config is returned as a JSON string
            if isinstance(config_data, str):
                try:
                    import json
                    config_data = json.loads(config_data)
                except json.JSONDecodeError:
                    print(f"Error parsing config for agent {agent_data.get('name')}: Invalid JSON")
                    config_data = {}

            model_conf = ModelConfig(**config_data.get("model_config", {}))
            rag_conf = RAGConfig(**config_data.get("rag_config", {}))
            
            config = AgentConfig(
                model_config=model_conf,
                rag_config=rag_conf,
                base_system_prompt=config_data.get("base_system_prompt", ""),
                specialized_system_prompt=config_data.get("specialized_system_prompt", "")
            )
            
            profiles.append(AgentProfile(
                name=agent_data["name"],
                description=agent_data["description"],
                config=config,
                enabled=agent_data["enabled"]
            ))
            
        return profiles

    def update_agent(self, name: str, config: AgentConfig) -> bool:
        """Updates an existing agent's configuration."""
        # Get current agent to preserve description
        agent_data = db.get_agent(name)
        if not agent_data:
            return False
        
        # Convert config to dict
        config_dict = {
            "model_config": {
                "litellm_model_name": config.model_config.litellm_model_name,
                "temperature": config.model_config.temperature,
                "max_tokens": config.model_config.max_tokens
            },
            "rag_config": {
                "corpus_id": config.rag_config.corpus_id,
                "corpus_name": config.rag_config.corpus_name
            },
            "base_system_prompt": config.base_system_prompt,
            "specialized_system_prompt": config.specialized_system_prompt
        }
        
        return db.create_agent(name, agent_data["description"], config_dict)

    def delete_agent(self, name: str) -> bool:
        """Deletes (disables) an agent profile and removes its RAG corpus."""
        
        # Get agent to retrieve corpus_id before deletion
        agent = self.get_agent(name)
        if not agent:
            print(f"[Registry] Agent '{name}' not found")
            return False
        
        # Delete the corpus from Vertex AI if it exists
        if agent.config.rag_config.corpus_id:
            corpus_id = agent.config.rag_config.corpus_id
            print(f"[Registry] Deleting corpus {corpus_id} for agent '{name}'...")
            
            if delete_corpus(corpus_id):
                print(f"[Registry] ✅ Corpus deleted")
            else:
                print(f"[Registry] ⚠️  Warning: Failed to delete corpus {corpus_id}")
                # Continue with agent deletion even if corpus deletion fails
        
        # Delete agent from database
        return db.delete_agent(name)

# Global registry instance
_registry = AgentRegistry()

def get_registry():
    return _registry
