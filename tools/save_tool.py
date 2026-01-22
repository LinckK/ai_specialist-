import os

def save_to_archive(file_name: str, content: str) -> str:
    """
    Saves content to a specified file in the 'agent_archives' directory.
    """
    print(f"\n--- Saving file: '{file_name}' ---")
    try:
        # Ensure the archive directory exists
        archive_dir = "agent_archives"
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
            
        file_path = os.path.join(archive_dir, file_name)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return f"Successfully saved content to {file_path}"
    except Exception as e:
        return f"Error saving file: {e}"
