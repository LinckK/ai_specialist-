"""
Tool for saving full conversation history to a file.
The agent can use this to save the entire chat conversation.
"""

import os
from datetime import datetime
from typing import Optional

def save_chat(conversation_history: list[dict], file_name: Optional[str] = None) -> str:
    """
    Save a full conversation history to a markdown file.
    
    Args:
        conversation_history: List of message dicts with 'role' and 'content' keys
        file_name: Optional filename (defaults to timestamp-based name)
        
    Returns:
        Success message with file path or error message
    """
    print(f"\n--- Saving chat conversation ---")
    
    if not conversation_history:
        return "Error: No conversation history to save."
    
    # Generate filename if not provided
    if not file_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"chat_{timestamp}.md"
    
    # Ensure .md extension
    if not file_name.endswith('.md'):
        file_name += '.md'
    
    # Ensure agent_archives directory exists
    archive_dir = "agent_archives"
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
    
    file_path = os.path.join(archive_dir, file_name)
    
    # Format as markdown
    content = f"# Conversa - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for msg in conversation_history:
        role = msg.get("role", "unknown")
        role_name = {
            "user": "👤 Usuário",
            "assistant": "🤖 Assistente",
            "error": "❌ Erro",
            "system": "⚙️ Sistema"
        }.get(role, role.capitalize())
        
        content += f"## {role_name}\n\n"
        
        # Add metadata if available
        if msg.get("tool_policy"):
            content += f"*Política de ferramentas: {msg['tool_policy']}*\n\n"
        if msg.get("timestamp"):
            content += f"*{msg['timestamp']}*\n\n"
        
        # Add content
        msg_content = msg.get("content", "")
        content += f"{msg_content}\n\n"
        content += "---\n\n"
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully saved conversation to {file_path} ({len(conversation_history)} messages)"
    except Exception as e:
        return f"Error saving conversation: {e}"

