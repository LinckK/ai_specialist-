"""
File Upload Tool for Vertex AI RAG Corpus

Handles uploading files to agent-specific RAG corpora with security checks.
Supports: PDF, TXT, MD, DOCX
"""

import os
import mimetypes
from pathlib import Path
from typing import Dict, Optional

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import vertexai
from vertexai import rag

# Configuration
PROJECT_ID = "agenticraga"
LOCATION = "europe-west1"
MAX_FILE_SIZE_MB = 32
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
GCS_STAGING_BUCKET = "agenticraga-rag-staging"

# Allowed file types
ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md', '.docx', '.doc'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'text/plain',
    'text/markdown',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/msword'
}

# Initialize Vertex AI
try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    print(f"[Upload Tool] Vertex AI initialized with project {PROJECT_ID}")
except Exception as e:
    print(f"[Upload Tool] Warning: Could not initialize Vertex AI: {e}")


def validate_file(file_path: str) -> tuple[bool, str]:
    """
    Validate file for upload.
    
    Args:
        file_path: Path to the file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(file_path)
    
    # Check if file exists
    if not path.exists():
        return False, f"File not found: {file_path}"
    
    # Check if it's a file (not directory)
    if not path.is_file():
        return False, f"Not a file: {file_path}"
    
    # Check file extension
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return False, f"Unsupported file type: {path.suffix}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size (Warn but allow for GCS fallback)
    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        # We now support larger files via GCS, so we just warn or allow
        # But let's keep a sane upper limit (e.g. 100MB) to prevent abuse if needed
        # For now, we'll allow it and let the GCS logic handle it.
        pass
    
    # Check MIME type
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False, f"Unsupported MIME type: {mime_type}"
    
    return True, ""


def upload_to_gcs(file_path: Path, bucket_name: str) -> str:
    """
    Uploads a file to GCS and returns the gs:// URI.
    """
    from google.cloud import storage
    
    print(f"[Upload Tool] Initializing GCS client for bucket: {bucket_name}")
    storage_client = storage.Client(project=PROJECT_ID)
    
    try:
        bucket = storage_client.get_bucket(bucket_name)
    except Exception:
        print(f"[Upload Tool] Bucket {bucket_name} not found. Creating...")
        bucket = storage_client.create_bucket(bucket_name, location=LOCATION)
        
    blob_name = file_path.name
    blob = bucket.blob(blob_name)
    
    print(f"[Upload Tool] Uploading {file_path} to gs://{bucket_name}/{blob_name}...")
    blob.upload_from_filename(str(file_path))
    
    return f"gs://{bucket_name}/{blob_name}"


def upload_file_to_corpus(file_path: str, corpus_id: str, display_name: Optional[str] = None) -> Dict[str, any]:
    """
    Upload a file to a Vertex AI RAG corpus.
    Handles large files by staging to GCS if needed.
    """
    # Validate file
    is_valid, error_msg = validate_file(file_path)
    if not is_valid:
        return {
            "success": False,
            "message": error_msg
        }
    
    try:
        path = Path(file_path)
        file_size = path.stat().st_size
        
        # Use filename as display name if not provided
        if not display_name:
            display_name = path.name
        
        print(f"[Upload Tool] Processing {display_name} ({file_size / 1024:.1f} KB)...")
        
        # Build corpus name
        corpus_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora/{corpus_id}"
        
        # STRATEGY: PDFs >1MB are problematic with direct upload. Use GCS staging earlier.
        # For PDFs: Use GCS if >1MB
        # For other files: Use GCS if >10MB
        is_pdf = path.suffix.lower() == '.pdf'
        upload_threshold = 1 * 1024 * 1024 if is_pdf else 10 * 1024 * 1024
        
        if file_size > upload_threshold:
            strategy = "GCS" if is_pdf else "GCS (large file)"
            print(f"[Upload Tool] File is {file_size / 1024:.1f} KB. Using {strategy} staging.")
            try:
                gcs_uri = upload_to_gcs(path, GCS_STAGING_BUCKET)
                print(f"[Upload Tool] Staged to {gcs_uri}. Importing to RAG...")
                
                # Import from GCS
                response = rag.import_files(
                    corpus_name=corpus_name,
                    paths=[gcs_uri]
                )
                
                print(f"[Upload Tool] ✅ Import triggered via GCS.")
                return {
                    "success": True,
                    "message": f"Successfully imported {display_name} via GCS staging",
                    "file_name": display_name,
                    "display_name": display_name,
                    "size_bytes": file_size,
                    "method": "gcs_import"
                }
                
            except Exception as gcs_e:
                print(f"[Upload Tool] ❌ GCS Import failed: {gcs_e}")
                import traceback
                traceback.print_exc()
                return {"success": False, "message": f"GCS Import failed: {str(gcs_e)}"}

        # --- DIRECT UPLOAD STRATEGY (Small files) ---
        print(f"[Upload Tool] Attempting direct upload...")
        
        # WORKAROUND: Copy to temp file with simple name to avoid SDK path issues on Windows
        import shutil
        import tempfile
        
        # Create a temp file with the same extension
        suffix = path.suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_path = Path(tmp.name)
        
        try:
            # Copy original file to temp path
            shutil.copy2(path, temp_path)
            
            # Upload from temp path with retry
            max_retries = 2
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    print(f"[Upload Tool] Direct upload attempt {attempt + 1}/{max_retries}...")
                    rag_file = rag.upload_file(
                        corpus_name=corpus_name,
                        path=str(temp_path.absolute()),
                        display_name=display_name,
                    )
                    
                    print(f"[Upload Tool] ✅ Direct upload complete: {rag_file.name}")
                    
                    return {
                        "success": True,
                        "message": f"Successfully uploaded {display_name}",
                        "file_name": rag_file.name,
                        "display_name": display_name,
                        "size_bytes": file_size,
                        "method": "direct_upload"
                    }
                    
                except Exception as direct_e:
                    last_error = direct_e
                    print(f"[Upload Tool] Direct upload attempt {attempt + 1} failed: {type(direct_e).__name__}: {str(direct_e)}")
                    
                    # If direct upload fails, fall back to GCS staging
                    if attempt == max_retries - 1:
                        print(f"[Upload Tool] Direct upload failed after {max_retries} attempts. Falling back to GCS staging...")
                        try:
                            gcs_uri = upload_to_gcs(path, GCS_STAGING_BUCKET)
                            print(f"[Upload Tool] Staged to {gcs_uri}. Importing to RAG...")
                            
                            response = rag.import_files(
                                corpus_name=corpus_name,
                                paths=[gcs_uri]
                            )
                            
                            print(f"[Upload Tool] ✅ GCS fallback successful.")
                            return {
                                "success": True,
                                "message": f"Successfully imported {display_name} via GCS fallback",
                                "file_name": display_name,
                                "display_name": display_name,
                                "size_bytes": file_size,
                                "method": "gcs_fallback"
                            }
                        except Exception as gcs_fallback_e:
                            print(f"[Upload Tool] ❌ GCS fallback also failed: {gcs_fallback_e}")
                            import traceback
                            traceback.print_exc()
                            raise  # Re-raise to be caught by outer exception handler
            
        finally:
            # Cleanup temp file
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = f"Upload failed: {str(e)}"
        print(f"[Upload Tool] ❌ {error_msg}")
        return {
            "success": False,
            "message": error_msg
        }


def upload_multiple_files(file_paths: list[str], corpus_id: str) -> Dict[str, any]:
    """
    Upload multiple files to a corpus.
    
    Args:
        file_paths: List of file paths
        corpus_id: Target corpus ID
    
    Returns:
        Dict with summary:
        {
            "total": int,
            "successful": int,
            "failed": int,
            "results": list[dict]
        }
    """
    results = []
    successful = 0
    failed = 0
    
    for file_path in file_paths:
        result = upload_file_to_corpus(file_path, corpus_id)
        results.append(result)
        
        if result["success"]:
            successful += 1
        else:
            failed += 1
    
    return {
        "total": len(file_paths),
        "successful": successful,
        "failed": failed,
        "results": results
    }


if __name__ == "__main__":
    import sys
    
    print("\n=== File Upload Tool Test ===\n")
    
    if len(sys.argv) < 3:
        print("Usage: python upload_tool.py <file_path> <corpus_id>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    corpus_id = sys.argv[2]
    
    # Test upload
    result = upload_file_to_corpus(file_path, corpus_id)
    
    if result["success"]:
        print(f"\n✅ Success: {result['message']}")
    else:
        print(f"\n❌ Failed: {result['message']}")
