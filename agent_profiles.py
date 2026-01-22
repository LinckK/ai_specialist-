"""
Agent Profile System for managing multiple specialized agents.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict
import json
import os
from .config import ModelConfig, RAGConfig

@dataclass
class AgentProfile:
    """Profile for a specialized agent."""
    name: str
    corpus_id: str
    specialized_prompt: str
    available_tools: List[str] = field(default_factory=lambda: ["rag_query", "google_search", "save_to_archive"])
    model_config: ModelConfig = field(default_factory=ModelConfig)
    default_model: str = "gemini/gemini-2.5-flash-lite"
    agent_id: Optional[str] = None  # Unique identifier
    
    def __post_init__(self):
        """Generate agent_id if not provided."""
        if self.agent_id is None:
            import uuid
            self.agent_id = str(uuid.uuid4())
    
    def to_dict(self) -> dict:
        """Convert profile to dictionary."""
        result = asdict(self)
        # Convert nested dataclasses
        result['model_config'] = asdict(self.model_config)
        return result
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentProfile':
        """Create profile from dictionary."""
        # Handle nested dataclasses
        if 'model_config' in data and isinstance(data['model_config'], dict):
            data['model_config'] = ModelConfig(**data['model_config'])
        return cls(**data)


class AgentRegistry:
    """Registry for managing agent profiles."""
    
    def __init__(self, registry_file: str = "agent_project/agent_registry.json"):
        self.registry_file = registry_file
        self.profiles: Dict[str, AgentProfile] = {}
        self.load_registry()
    
    def load_registry(self):
        """Load agent profiles from JSON file."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles = {
                        agent_id: AgentProfile.from_dict(profile_data)
                        for agent_id, profile_data in data.items()
                    }
                print(f"Loaded {len(self.profiles)} agent profiles")
            except Exception as e:
                print(f"Error loading agent registry: {e}")
                self.profiles = {}
        else:
            # Create default agent if registry doesn't exist
            self.create_default_agent()
            self.save_registry()
    
    def save_registry(self):
        """Save agent profiles to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
            data = {
                agent_id: profile.to_dict()
                for agent_id, profile in self.profiles.items()
            }
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving agent registry: {e}")
    
    def create_default_agent(self):
        """Create a default agent profile."""
        default_profile = AgentProfile(
            name="Default Agent",
            corpus_id="2305843009213693952",
            specialized_prompt="""**[INSTRUÇÃO ESPECIALIZADA: ATUE COMO UM ESPECIALISTA ESTRATÉGICO EM COMUNICAÇÃO E INFLUÊNCIA]**

Sua missão é desenvolver um guia abrangente para um líder moderno sobre como melhorar o moral da equipe, especialmente em um ambiente de trabalho híbrido ou remoto. Este guia deve incorporar as últimas descobertas sobre tendências de comunicação digital, ao mesmo tempo em que fundamenta os conselhos em princípios atemporais de relações humanas. O resultado final deve ser um relatório bem estruturado.
""",
            available_tools=["rag_query", "google_search", "save_to_archive"],
            default_model="gemini/gemini-2.5-flash-lite"
        )
        self.profiles[default_profile.agent_id] = default_profile
    
    def add_profile(self, profile: AgentProfile) -> str:
        """Add or update an agent profile."""
        self.profiles[profile.agent_id] = profile
        self.save_registry()
        return profile.agent_id
    
    def get_profile(self, agent_id: str) -> Optional[AgentProfile]:
        """Get agent profile by ID."""
        return self.profiles.get(agent_id)
    
    def get_profile_by_name(self, name: str) -> Optional[AgentProfile]:
        """Get agent profile by name."""
        for profile in self.profiles.values():
            if profile.name == name:
                return profile
        return None
    
    def remove_profile(self, agent_id: str) -> bool:
        """Remove an agent profile."""
        if agent_id in self.profiles:
            del self.profiles[agent_id]
            self.save_registry()
            return True
        return False
    
    def list_profiles(self) -> List[AgentProfile]:
        """List all agent profiles."""
        return list(self.profiles.values())
    
    def update_profile(self, agent_id: str, **updates) -> bool:
        """Update an agent profile with new values."""
        if agent_id not in self.profiles:
            return False
        
        profile = self.profiles[agent_id]
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        self.save_registry()
        return True


# Global registry instance
_registry_instance: Optional[AgentRegistry] = None

def get_registry() -> AgentRegistry:
    """Get the global agent registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    return _registry_instance

