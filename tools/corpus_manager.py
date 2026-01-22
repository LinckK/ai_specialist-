"""
Vertex AI RAG Corpus Management Utilities

Provides functions for creating, deleting, and managing Vertex AI RAG corpora.
Each agent has its own dedicated corpus for isolated knowledge bases.
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Any

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import vertexai
try:
    from vertexai import rag
except ImportError:
    print("[Corpus Manager] Warning: Could not import 'rag' from 'vertexai'. RAG corpus management will be disabled.")
    rag = None

# Configuration
PROJECT_ID = "agenticraga"
LOCATION = "europe-west1"

# Initialize Vertex AI
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print("[Corpus Manager] Vertex AI initialized")
except Exception as e:
    print(f"[Corpus Manager] Warning: Could not initialize Vertex AI: {e}")


def create_corpus(display_name: str, description: str = "") -> Optional[str]:
    """
    Create a new RAG corpus in Vertex AI.
    
    Args:
        display_name: Human-readable name for the corpus
        description: Optional description of the corpus
    
    Returns:
        Corpus ID (numeric string) on success, None on failure
    """
    try:
        print(f"[Corpus Manager] Creating corpus: {display_name}")
        
        # Create corpus using Vertex AI RAG API
        corpus = rag.create_corpus(
            display_name=display_name,
            description=description or f"Knowledge base for {display_name}"
        )
        
        # Extract corpus ID from the resource name
        # Format: projects/{project}/locations/{location}/ragCorpora/{corpus_id}
        corpus_id = corpus.name.split("/")[-1]
        
        print(f"[Corpus Manager] ✅ Created corpus: {corpus_id}")
        return corpus_id
        
    except Exception as e:
        print(f"[Corpus Manager] ❌ Error creating corpus: {e}")
        return None


def delete_corpus(corpus_id: str) -> bool:
    """
    Delete a RAG corpus from Vertex AI.
    
    Args:
        corpus_id: The numeric corpus ID
    
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        print(f"[Corpus Manager] Deleting corpus: {corpus_id}")
        
        # Build full corpus name
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        
        # Delete the corpus
        rag.delete_corpus(name=corpus_name)
        
        print(f"[Corpus Manager] ✅ Deleted corpus: {corpus_id}")
        return True
        
    except Exception as e:
        print(f"[Corpus Manager] ❌ Error deleting corpus: {e}")
        return False


def get_corpus_info(corpus_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a RAG corpus.
    
    Args:
        corpus_id: The numeric corpus ID
    
    Returns:
        Dictionary with corpus metadata, or None if not found
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        
        corpus = rag.get_corpus(name=corpus_name)
        
        return {
            "name": corpus.name,
            "display_name": corpus.display_name,
            "description": corpus.description,
            "create_time": str(corpus.create_time) if hasattr(corpus, 'create_time') else None,
        }
        
    except Exception as e:
        print(f"[Corpus Manager] Error getting corpus info: {e}")
        return None


def list_corpus_files(corpus_id: str) -> List[Dict[str, Any]]:
    """
    List all files in a RAG corpus.
    
    Args:
        corpus_id: The numeric corpus ID
    
    Returns:
        List of file metadata dictionaries
    """
    try:
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        
        # List files in the corpus
        files = rag.list_files(corpus_name=corpus_name)
        
        file_list = []
        for rag_file in files:
            file_list.append({
                "name": rag_file.name,
                "display_name": rag_file.display_name,
                "size_bytes": getattr(rag_file, 'size_bytes', 'Unknown'),
            })
        
        return file_list
        
    except Exception as e:
        print(f"[Corpus Manager] Error listing files: {e}")
        return []


def corpus_exists(corpus_id: str) -> bool:
    """
    Check if a corpus exists.
    
    Args:
        corpus_id: The numeric corpus ID
    
    Returns:
        True if corpus exists, False otherwise
    """
    return get_corpus_info(corpus_id) is not None


if __name__ == "__main__":
    # Test corpus operations
    print("\n=== Testing Corpus Manager ===\n")
    
    # Test 1: Create corpus
    test_corpus_id = create_corpus("test_corpus", "Test corpus for validation")
    
    if test_corpus_id:
        print(f"\n✅ Created test corpus: {test_corpus_id}")
        
        # Test 2: Get corpus info
        info = get_corpus_info(test_corpus_id)
        print(f"\n📋 Corpus Info: {info}")
        
        # Test 3: List files (should be empty)
        files = list_corpus_files(test_corpus_id)
        print(f"\n📁 Files in corpus: {len(files)}")
        
        # Test 4: Delete corpus
        deleted = delete_corpus(test_corpus_id)
        print(f"\n🗑️  Corpus deleted: {deleted}")
    else:
        print("\n❌ Failed to create test corpus")
