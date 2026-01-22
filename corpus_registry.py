"""
Corpus Registry for managing multiple RAG corpuses.
Maps agent names to their associated corpus IDs.
"""

from typing import Dict, Optional
import json
import os

class CorpusRegistry:
    """Registry for managing RAG corpus mappings."""
    
    def __init__(self, registry_file: str = "agent_project/corpus_registry.json"):
        self.registry_file = registry_file
        self.registry: Dict[str, str] = {}
        self.load_registry()
    
    def load_registry(self):
        """Load corpus registry from JSON file."""
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    self.registry = json.load(f)
                print(f"Loaded corpus registry with {len(self.registry)} entries")
            except Exception as e:
                print(f"Error loading corpus registry: {e}")
                self.registry = {}
        else:
            # Create default registry
            self.registry = {
                "default": "2305843009213693952"  # Default corpus ID
            }
            self.save_registry()
    
    def save_registry(self):
        """Save corpus registry to JSON file."""
        try:
            os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving corpus registry: {e}")
    
    def get_corpus_id(self, agent_name: str) -> Optional[str]:
        """Get corpus ID for an agent."""
        return self.registry.get(agent_name)
    
    def register_corpus(self, agent_name: str, corpus_id: str):
        """Register a corpus ID for an agent."""
        self.registry[agent_name] = corpus_id
        self.save_registry()
        print(f"Registered corpus {corpus_id} for agent '{agent_name}'")
    
    def remove_corpus(self, agent_name: str) -> bool:
        """Remove corpus registration for an agent."""
        if agent_name in self.registry:
            del self.registry[agent_name]
            self.save_registry()
            return True
        return False
    
    def list_corpuses(self) -> Dict[str, str]:
        """List all registered corpuses."""
        return self.registry.copy()

# Global registry instance
_registry_instance: Optional[CorpusRegistry] = None

def get_registry() -> CorpusRegistry:
    """Get the global corpus registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = CorpusRegistry()
    return _registry_instance

