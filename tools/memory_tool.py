import os
from typing import Optional

GLOBAL_MEMORY_FILE = "agent_memory.md" # Removed leading dot for visibility inside folder

def get_memory_path(workspace_root: str, conversation_id: str = None) -> str:
    # Define the memory directory
    memory_dir = os.path.join(workspace_root, "chats_memory")
    
    # Ensure directory exists
    if not os.path.exists(memory_dir):
        os.makedirs(memory_dir, exist_ok=True)
        
    if conversation_id:
        # Sanitize ID just in case
        safe_id = "".join(c for c in conversation_id if c.isalnum() or c in ('-', '_'))
        return os.path.join(memory_dir, f"memory_{safe_id}.md") # Removed leading dot
    return os.path.join(memory_dir, GLOBAL_MEMORY_FILE)

def update_memory(content: str, mode: str = "append", workspace_root: str = None, conversation_id: str = None) -> str:
    """
    Updates the agent's persistent memory file.
    
    Args:
        content: The text to add or write.
        mode: 'append' to add to existing memory, 'overwrite' to replace it.
        workspace_root: Root directory (injected by agent).
        conversation_id: ID of the current conversation (injected by agent).
    """
    if not workspace_root:
        # Fallback for testing
        workspace_root = os.getcwd()
        
    file_path = get_memory_path(workspace_root, conversation_id)
    
    try:
        if mode == "overwrite":
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Memory overwritten for chat {conversation_id or 'GLOBAL'}. Current size: {len(content)} chars."
            
        else: # append
            # Read existing to ensure we add a newline if needed
            existing = ""
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    existing = f.read()
            
            new_content = existing
            if existing and not existing.endswith("\n"):
                new_content += "\n"
            new_content += f"- {content}"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Memory updated for chat {conversation_id or 'GLOBAL'}. Added: '{content}'"
            
    except Exception as e:
        return f"Failed to update memory: {str(e)}"

def read_memory(workspace_root: str = None, conversation_id: str = None) -> str:
    """Reads the current memory content."""
    if not workspace_root:
        workspace_root = os.getcwd()
        
    file_path = get_memory_path(workspace_root, conversation_id)
    
    if not os.path.exists(file_path):
        return ""
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading memory: {str(e)}"

# Tool definition for the agent
update_memory_tool_definition = {
    "type": "function",
    "function": {
        "name": "update_memory",
        "description": "🧠 [MEMORY SYSTEM] Salva informações CRÍTICAS que o usuário disse para não esquecer (ex: preferências, restrições, decisões de projeto). Use isso para manter um 'estado' persistente da conversa.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "A informação a ser lembrada (ex: 'O usuário prefere tom formal', 'O projeto é sobre X')."
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "overwrite"],
                    "description": "Use 'append' para adicionar fatos, 'overwrite' para reescrever o resumo do zero."
                }
            },
            "required": ["content"]
        }
    }
}
