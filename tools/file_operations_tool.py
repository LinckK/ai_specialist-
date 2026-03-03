"""
Comprehensive file operations tool for the agent.
Allows listing files, reading files, writing files, creating directories, etc.
SIMPLIFIED - No sandbox, permissions checked before execution in agent.py
"""

import os
from pathlib import Path
from typing import Optional
from agent_project.config import WORKSPACE_ROOT

def _resolve_path(path_str: str) -> Path:
    """
    Resolves a path relative to the WORKSPACE_ROOT.
    If an absolute path is provided, it is used as is (but ideally should be within workspace).
    If a relative path is provided, it is joined with WORKSPACE_ROOT.
    """
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    else:
        return (Path(WORKSPACE_ROOT) / path).resolve()

def list_files(directory: str = ".", pattern: Optional[str] = None) -> str:
    """
    List files and directories in a given path.
    
    Args:
        directory: Directory path to list (default: current directory)
        pattern: Optional glob pattern to filter files (e.g., "*.py", "*.md")
        
    Returns:
        Formatted list of files and directories
    """
    # If directory is ".", list WORKSPACE_ROOT
    if directory == ".":
        target_dir = Path(WORKSPACE_ROOT)
    else:
        target_dir = _resolve_path(directory)
        
    print(f"\n--- Listing files in: {target_dir} ---")
    
    try:
        if not target_dir.exists():
            return f"Error: Directory '{target_dir}' does not exist."
        
        if not target_dir.is_dir():
            return f"Error: '{target_dir}' is not a directory."
        
        items = []
        if pattern:
            # Use glob pattern
            for item in target_dir.glob(pattern):
                items.append(item)
        else:
            # List all items
            for item in target_dir.iterdir():
                items.append(item)
        
        if not items:
            return f"No files found in '{target_dir}'" + (f" matching pattern '{pattern}'" if pattern else "")
        
        # Sort: directories first, then files
        dirs = [item for item in items if item.is_dir()]
        files = [item for item in items if item.is_file()]
        
        result = f"Directory: {target_dir}\n\n"
        
        if dirs:
            result += "Directories:\n"
            for d in sorted(dirs):
                result += f"  📁 {d.name}/\n"
            result += "\n"
        
        if files:
            result += "Files:\n"
            for f in sorted(files):
                size = f.stat().st_size
                size_str = f"{size:,} bytes" if size < 1024 else f"{size/1024:.1f} KB"
                result += f"  📄 {f.name} ({size_str})\n"
        
        return result.strip()
        
    except Exception as e:
        return f"Error listing files: {e}"

def _transcribe_multimodal_file(file_path: Path, mime_type: str) -> dict:
    """
    Uses Gemini Vision (Multimodal) to transcribe images or scanned PDFs.
    """
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part
        
        # Hardcoded config matches rag_tool.py
        PROJECT_ID = "agenticraga" 
        LOCATION = "us-west1"
        
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        
        # Use a fast multimodal model
        model = GenerativeModel("gemini-1.5-flash-002")
        
        with open(file_path, "rb") as f:
            file_data = f.read()
            
        part = Part.from_data(data=file_data, mime_type=mime_type)
        
        prompt = """
        TASK: Transcribe this document/image exactly.
        - If it is a contract, capture every clause, signature, and detail.
        - If it contains charts or graphs, describe the data structure and values in detail.
        - If it is handwritten, transcribe it to the best of your ability.
        - Output ONLY the text content.
        """
        
        response = model.generate_content([part, prompt])
        return {"success": True, "text": response.text}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def read_file(file_path: str, max_lines: Optional[int] = None) -> str:
    """
    Lê o conteúdo exato de um arquivo existente.
    Suporta:
    - Textos (.txt, .md, .py, etc)
    - PDFs (Texto selecionável + OCR para escaneados)
    - Imagens (.png, .jpg, .jpeg) -> Transcrição via Vision AI
    """
    target_file = _resolve_path(file_path)
    print(f"\n--- Reading file: {target_file} ---")
    
    suffix = target_file.suffix.lower()
    
    # 1. IMAGE HANDLING (OCR)
    if suffix in ['.png', '.jpg', '.jpeg']:
        print(f"[FileOps] Image detected. Using Gemini Vision OCR...")
        mime_type = "image/png" if suffix == '.png' else "image/jpeg"
        ocr_result = _transcribe_multimodal_file(target_file, mime_type)
        
        if ocr_result["success"]:
            return f"Analyzed Image: {target_file.name}\n[DEBUG: MODE=VISION OCR]\n========================================\n{ocr_result['text']}"
        else:
            return f"Error reading image: {ocr_result['error']}"

    # 2. PDF HANDLING (Hybrid: pypdf -> Vision Fallback)
    if suffix == '.pdf':
        try:
            print(f"[FileOps] Reading PDF: {target_file}")
            from pypdf import PdfReader
            
            reader = PdfReader(str(target_file))
            num_pages = len(reader.pages)
            extracted_text = ""
            
            # Read first 50 pages text
            max_pdf_pages = 50 
            pages_read = 0
            
            for i, page in enumerate(reader.pages):
                if i >= max_pdf_pages:
                    extracted_text += f"\n\n[TRUNCATED] Stopped basic read after {max_pdf_pages} pages."
                    break
                text = page.extract_text()
                if text:
                    extracted_text += f"\n--- Page {i+1} ---\n{text}"
                pages_read += 1
            
            char_count = len(extracted_text)
            is_scanned = char_count < 100 and num_pages > 0
            
            result_header = f"Analyzed PDF: {target_file.name}\n"
            result_header += f"========================================\n"
            result_header += f"[DEBUG INDICATORS]\n"
            result_header += f"- Pages: {num_pages}\n"
            result_header += f"- Text Layer Chars: {char_count}\n"
            
            # FALLBACK TO OCR IF SCANNED
            if is_scanned:
                print(f"[FileOps] PDF appears scanned (only {char_count} chars). Switching to Gemini Vision OCR...")
                result_header += f"- Mode: ⚠️ SCANNED (Switching to Vision AI)\n"
                result_header += f"========================================\n\n"
                
                ocr_result = _transcribe_multimodal_file(target_file, "application/pdf")
                if ocr_result["success"]:
                    return result_header + ocr_result["text"]
                else:
                    return result_header + f"[ERROR] Vision OCR failed: {ocr_result['error']}"
            else:
                result_header += f"- Mode: ✅ TEXT LAYER\n"
                result_header += f"========================================\n\n"
                return result_header + extracted_text
            
        except ImportError:
            return "Error: pypdf library not found. Please install it: pip install pypdf"
        except Exception as e:
            return f"Error reading PDF: {e}"

    # 3. DOCX HANDLING
    if suffix == '.docx':
        try:
            print(f"[FileOps] Reading DOCX: {target_file}")
            import docx
            doc = docx.Document(target_file)
            extracted_text = "\n".join([para.text for para in doc.paragraphs])
            
            result_header = f"Analyzed DOCX: {target_file.name}\n"
            result_header += f"========================================\n\n"
            return result_header + extracted_text
        except ImportError:
            return "Error: python-docx library not found. Please install it: pip install python-docx"
        except Exception as e:
            return f"Error reading DOCX: {e}"

    # 4. TEXT HANDLING (Standard)
    BINARY_EXTENSIONS = {
        '.exe', '.dll', '.bin', '.zip', '.tar', '.gz', 
        '.ico', '.xlsx', '.pptx', 
        '.pyc', '.obj', '.db', '.sqlite'
    }

    if target_file.suffix.lower() in BINARY_EXTENSIONS:
        msg = f"Error: Cannot read binary file type '{target_file.suffix}' as text. Use specific tools for this format."
        print(f"[RAG Hygiene] Blocked reading of binary file: {target_file.name}")
        return msg
    
    try:
        if not target_file.exists():
            return f"Error: File '{target_file}' does not exist."
        
        if not target_file.is_file():
            return f"Error: '{target_file}' is not a file."
        
        # Check file size (warn if very large)
        size = target_file.stat().st_size
        if size > 1_000_000:  # 1MB
            return f"Error: File '{target_file}' is too large ({size/1_000_000:.1f} MB). Use max_lines parameter or read specific sections."
        
        with open(target_file, 'r', encoding='utf-8', errors='replace') as f:
            if max_lines:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"\n... (file truncated, showing first {max_lines} lines)")
                        break
                    lines.append(line)
                content = ''.join(lines)
            else:
                content = f.read()
        
        return f"Contents of {target_file}:\n\n{content}"
        
    except Exception as e:
        # v6.3: RAG Hygiene - Logging
        try:
            with open("RAG_DEBUG.md", "a", encoding="utf-8") as log:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log.write(f"## [{timestamp}] Read Error\n**File:** {target_file}\n**Error:** {str(e)}\n\n---\n\n")
        except:
            pass # Failsafe
            
        return f"Error reading file: {e}"

def write_file(file_path: str, content: str, append: bool = False, writing_plan: str = None) -> str:
    """
    [ESCRITA DE ARQUIVOS COM PLANEJAMENTO]
    Escreve ou anexa conteúdo a um arquivo com rastreamento de progresso.

    REGRAS DE SEGURANÇA:
    1. NUNCA escreva na raiz. Use subpastas semânticas (ex: 'Relatorios/Semana1/report.md').
    2. ARQUIVOS GRANDES: Use 'append=True' e escreva em blocos.
    
    PROTOCOLO DE PLANEJAMENTO (OBRIGATÓRIO para arquivos grandes):
    1. PRIMEIRA CHAMADA: Defina seu plano completo
       write_file("doc.md", parte1, append=False, 
                  writing_plan="1. Introdução\n2. Capítulo 1\n3. Capítulo 2\n4. Conclusão")
    
    2. CHAMADAS SEGUINTES: O sistema mostrará automaticamente:
       - ✅ O que já foi escrito (últimos 500 chars)
       - 📋 O plano original (para não esquecer o que falta)
       - 📊 Progresso estimado
       
    3. MARQUE O PROGRESSO: Em cada append, indique qual parte você está completando
       write_file("doc.md", capitulo2, append=True, 
                  writing_plan="COMPLETANDO: Capítulo 2")
    """
    target_file = _resolve_path(file_path)
    plan_file = target_file.parent / f".{target_file.name}.plan"
    
    mode_desc = "Appending" if append else "Writing"
    content_size = len(content)
    print(f"\n--- {mode_desc} to file: {target_file} ({content_size} chars) ---")
    
    try:
        # Ensure parent directory exists
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        # === PLANNING SYSTEM ===
        
        # Save plan if provided
        if writing_plan and not append:
            # New file - save the master plan
            with open(plan_file, 'w', encoding='utf-8') as f:
                f.write(f"MASTER PLAN:\n{writing_plan}\n\nPROGRESS LOG:\n")
            print(f"📋 [Plan Saved] Master plan stored in {plan_file.name}")
        
        # Load and show existing plan when appending
        context_info = ""
        if append and target_file.exists():
            # Read existing file content
            try:
                with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
                    existing_content = f.read()
                    existing_size = len(existing_content)
                    
                    # Show last 500 chars as context
                    if existing_size > 500:
                        last_content = existing_content[-500:]
                        context_info += f"\n{'='*60}\n"
                        context_info += f"✅ ALREADY WRITTEN ({existing_size} chars total)\n"
                        context_info += f"{'='*60}\n"
                        context_info += f"...{last_content}\n"
                    else:
                        context_info += f"\n{'='*60}\n"
                        context_info += f"✅ CURRENT FILE ({existing_size} chars)\n"
                        context_info += f"{'='*60}\n"
                        context_info += f"{existing_content}\n"
            except Exception as e:
                print(f"[Warning] Could not read existing content: {e}")
            
            # Show the master plan
            if plan_file.exists():
                try:
                    with open(plan_file, 'r', encoding='utf-8') as f:
                        plan_content = f.read()
                        context_info += f"\n{'='*60}\n"
                        context_info += f"📋 YOUR ORIGINAL PLAN (don't forget!)\n"
                        context_info += f"{'='*60}\n"
                        context_info += f"{plan_content}\n"
                        context_info += f"{'='*60}\n"
                except Exception as e:
                    print(f"[Warning] Could not read plan: {e}")
            
            # Update progress log if new progress is provided
            if writing_plan and plan_file.exists():
                try:
                    with open(plan_file, 'a', encoding='utf-8') as f:
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        f.write(f"[{timestamp}] {writing_plan}\n")
                    print(f"📊 [Progress Updated] {writing_plan}")
                except Exception as e:
                    print(f"[Warning] Could not update progress: {e}")
        
        # Print context info
        if context_info:
            print(context_info)
        
        # === LARGE FILE WARNING ===
        if not append and content_size > 50000:
            print(f"\n⚠️  [LARGE FILE DETECTED] ({content_size} chars)")
            print(f"   CRITICAL: You are writing a large file in ONE call!")
            print(f"   RECOMMENDATION: Split into blocks with a PLAN")
            print(f"   \n   Example:")
            print(f"     write_file('doc.md', intro, append=False,")
            print(f"                writing_plan='1. Intro\\n2. Body\\n3. Conclusion')")
            print(f"     write_file('doc.md', body, append=True,")
            print(f"                writing_plan='COMPLETANDO: Body')")
            print(f"     write_file('doc.md', conclusion, append=True,")
            print(f"                writing_plan='COMPLETANDO: Conclusion')\n")
        
        # === WRITE THE FILE ===
        write_mode = "a" if append else "w"
        with open(target_file, write_mode, encoding="utf-8") as f:
            f.write(content)
        
        # Calculate total size after write
        total_size = target_file.stat().st_size
        action = "appended to" if append else "written to"
        
        result = f"✅ Successfully {action} {target_file}\n"
        result += f"   Added: {content_size} chars"
        if append:
            result += f" | Total file: {total_size} bytes"
        
        return result
        
    except Exception as e:
        return f"❌ Error writing file: {e}"

def create_directory(directory_path: str) -> str:
    """
    Create a directory.
    
    Args:
        directory_path: Path to the directory to create
        
    Returns:
        Success message or error message
    """
    target_dir = _resolve_path(directory_path)
    print(f"\n--- Creating directory: {target_dir} ---")
    
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return f"Directory created: {target_dir}"
        
    except Exception as e:
        return f"Error creating directory: {e}"

def delete_file(file_path: str) -> str:
    """
    Delete a file.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        Success message or error message
    """
    target_file = _resolve_path(file_path)
    print(f"\n--- Deleting file: {target_file} ---")
    
    try:
        if not target_file.exists():
            return f"Error: File '{target_file}' does not exist."
            
        if not target_file.is_file():
            return f"Error: '{target_file}' is not a file."
            
        target_file.unlink()
        return f"Successfully deleted {target_file}"
        
    except Exception as e:
        return f"Error deleting file: {e}"
