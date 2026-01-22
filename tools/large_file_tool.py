import os
from pathlib import Path
from typing import Dict, Any
from agent_project.config import WORKSPACE_ROOT

def _resolve_path(path_str: str) -> Path:
    """Resolves path relative to WORKSPACE_ROOT."""
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    else:
        return (Path(WORKSPACE_ROOT) / path).resolve()

def write_large_file(file_path: str, content: str, chunk_size: int = 50000) -> Dict[str, Any]:
    """
    Writes large files with automatic chunking if needed.
    
    Args:
        file_path: Path to the file to write.
        content: Full content to write (can be very large).
        chunk_size: Characters per chunk (default: 50000, ~12500 tokens).
        
    Returns:
        Dict with status and details about the operation.
    """
    target_path = _resolve_path(file_path)
    print(f"\n--- Writing Large File: '{target_path}' ({len(content)} chars) ---")
    
    try:
        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # If content is small enough, write directly
        if len(content) <= chunk_size:
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {
                "status": "Success",
                "message": f"File written successfully ({len(content)} chars)",
                "chunks": 1
            }
        
        # Content is large, split into chunks
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
        
        print(f"[Large File] Splitting into {len(chunks)} chunks...")
        
        # Write first chunk (overwrite mode)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(chunks[0])
        
        # Append remaining chunks
        for i, chunk in enumerate(chunks[1:], start=2):
            with open(target_path, 'a', encoding='utf-8') as f:
                f.write(chunk)
            print(f"[Large File] Wrote chunk {i}/{len(chunks)}")
        
        return {
            "status": "Success",
            "message": f"Large file written successfully ({len(content)} chars in {len(chunks)} chunks)",
            "chunks": len(chunks),
            "file_size": len(content)
        }
        
    except Exception as e:
        return {
            "status": "Error",
            "message": f"Failed to write large file: {e}"
        }


def smart_write_file(file_path: str, content: str, append: bool = False, auto_chunk: bool = True) -> Dict[str, Any]:
    """
    Intelligent file writing with automatic large file handling.
    
    Args:
        file_path: Path to the file.
        content: Content to write.
        append: If True, append to existing file (default: False).
        auto_chunk: If True, automatically chunk large files (default: True).
        
    Returns:
        Dict with operation status.
    """
    target_path = _resolve_path(file_path)
    
    # If appending or content is small, use standard write
    if append or not auto_chunk or len(content) <= 50000:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            mode = 'a' if append else 'w'
            with open(target_path, mode, encoding='utf-8') as f:
                f.write(content)
            return {
                "status": "Success",
                "message": f"File {'appended to' if append else 'written'} successfully"
            }
        except Exception as e:
            return {"status": "Error", "message": str(e)}
    
    # Use chunked writing for large files
    return write_large_file(file_path, content)
