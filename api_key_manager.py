"""
API Key Manager for secure storage and retrieval of API keys per provider.
"""

import os
import json
from typing import Optional, Dict

# Optional encryption support
try:
    from cryptography.fernet import Fernet
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    Fernet = None

class APIKeyManager:
    """Manages API keys for different providers with optional encryption."""
    
    def __init__(self, storage_file: str = "agent_project/api_keys.json", encrypt: bool = False):
        self.storage_file = storage_file
        self.encrypt = encrypt
        self.keys: Dict[str, str] = {}
        
        # Generate or load encryption key
        if encrypt:
            self._init_encryption()
        
        self.load_keys()
    
    def _init_encryption(self):
        """Initialize encryption key."""
        if not CRYPTOGRAPHY_AVAILABLE:
            raise ImportError("cryptography package is required for encryption. Install it with: pip install cryptography")
        
        key_file = "agent_project/.encryption_key"
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                self.cipher_key = f.read()
        else:
            self.cipher_key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(self.cipher_key)
        
        self.cipher = Fernet(self.cipher_key)
    
    def _encrypt(self, value: str) -> str:
        """Encrypt a value."""
        if not self.encrypt:
            return value
        return self.cipher.encrypt(value.encode()).decode()
    
    def _decrypt(self, value: str) -> str:
        """Decrypt a value."""
        if not self.encrypt:
            return value
        return self.cipher.decrypt(value.encode()).decode()
    
    def load_keys(self):
        """Load API keys from storage file."""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Decrypt if needed
                    self.keys = {
                        provider: self._decrypt(encrypted_key)
                        for provider, encrypted_key in data.items()
                    }
            except Exception as e:
                print(f"Error loading API keys: {e}")
                self.keys = {}
        else:
            self.keys = {}
    
    def save_keys(self):
        """Save API keys to storage file."""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            # Encrypt if needed
            data = {
                provider: self._encrypt(key)
                for provider, key in self.keys.items()
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving API keys: {e}")
    
    def set_key(self, provider: str, api_key: str):
        """Set API key for a provider."""
        self.keys[provider] = api_key
        self.save_keys()
    
    def get_key(self, provider: str) -> Optional[str]:
        """Get API key for a provider."""
        # First check stored keys
        if provider in self.keys:
            return self.keys[provider]
        
        # Fallback to environment variables
        env_mapping = {
            "gemini": "GEMINIFLASH_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        
        env_var = env_mapping.get(provider.lower())
        if env_var:
            return os.getenv(env_var)
        
        return None
    
    def remove_key(self, provider: str) -> bool:
        """Remove API key for a provider."""
        if provider in self.keys:
            del self.keys[provider]
            self.save_keys()
            return True
        return False
    
    def list_keys(self, mask: bool = True) -> Dict[str, str]:
        """List all stored API keys (optionally masked)."""
        if mask:
            return {
                provider: f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
                for provider, key in self.keys.items()
            }
        return self.keys.copy()
    
    def has_key(self, provider: str) -> bool:
        """Check if a provider has a configured key."""
        return self.get_key(provider) is not None


# Global manager instance
_manager_instance: Optional[APIKeyManager] = None

def get_manager(encrypt: bool = False) -> APIKeyManager:
    """Get the global API key manager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = APIKeyManager(encrypt=encrypt)
    return _manager_instance

