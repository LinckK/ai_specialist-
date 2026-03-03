import os
import json
import time
from typing import List, Dict, Any, Union, Callable, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import litellm
import argparse

# Enable litellm's verbose debugging (updated for new version)
os.environ['LITELLM_LOG'] = 'DEBUG'
litellm.drop_params = True # Drop unsupported params like presence_penalty for Gemini

# --- Rate Limit Retry Helper (No Fallback) ---
def completion_with_retry(max_retries: int = 3, initial_delay: float = 20.0, **kwargs):
    """
    Wrapper for litellm.completion with automatic retry on 429 errors.
    Uses exponential backoff: 20s -> 30s -> 45s
    NO fallback to other models - waits for quota to reset.
    """
    model_name = kwargs.get("model", "unknown")
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = litellm.completion(**kwargs)
            
            # --- DEBUG: Inspect Empty Responses ---
            if response and len(response.choices) > 0:
                first_choice = response.choices[0]
                if not first_choice.message.content and not first_choice.message.tool_calls:
                     print(f"\n[DEBUG] ⚠️  EMPTY CONTENT DETECTED! (Attempt {attempt+1}/{max_retries})")
                     print(f"[DEBUG] Finish Reason: {first_choice.finish_reason}")
                     
                     # FORCE RETRY: Treat empty content as a failure
                     if attempt < max_retries:
                         print(f"[Retry] Model returned empty content. Retrying...")
                         time.sleep(delay)
                         delay = min(delay * 1.5, 60)
                         continue
                     else:
                         print(f"[Error] Max retries reached with empty content.")
            # -------------------------------------
            
            return response
        except litellm.exceptions.RateLimitError as e:
            last_error = e
            # Log the FULL error for debugging
            error_details = str(e)
            print(f"\n[429 DEBUG] Full error: {error_details[:500]}")
            
            if attempt < max_retries:
                print(f"[Retry] Rate limit on {model_name}. Waiting {delay:.0f}s... ({attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay = min(delay * 1.5, 60)
            else:
                raise e
        except Exception as e:
            raise e
    
    raise last_error

# Import our custom tool functions - BASIC TOOLS
from .tools.rag_tool import rag_query
from .tools.search_tool import google_search
from .tools.deep_search_tool import deep_search
from .tools.save_tool import save_to_archive
from .tools.cmd_tool import execute_cmd
from .tools.save_chat_tool import save_chat
from .tools.file_operations_tool import list_files, read_file, write_file, create_directory, delete_file
from .tools.document_tool import create_word_document
from .tools.call_agent_tool import call_agent
from .tools.inspection_tool import view_agent_details
from .tools.memory_tool import update_memory, read_memory, update_memory_tool_definition
from .tools.consult_expert_tool import consult_expert

# Import the new configuration system
from .config import AgentConfig, get_default_config

# --- Configuration ---
load_dotenv() # Load environment variables from .env file

# Ensure GEMINI_API_KEY is set for litellm to use AI Studio (needed for Gemini 3)
if os.getenv("GEMINIFLASH_API_KEY") and not os.getenv("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = os.getenv("GEMINIFLASH_API_KEY")

# The model and max iterations are now managed by the config, but we can keep a fallback here if needed.
MAX_ITERATIONS = 10

# --- Tool Definitions (for litellm/OpenAI compatible API) ---
rag_query_tool_definition = {
    "type": "function",
    "function": {
        "name": "rag_query",
        "description": "⚠️ [MEMORY MODULE] Acesso à Base de Conhecimento (Long-Term Memory). OBRIGATÓRIO para qualquer tópico técnico, regras de negócio ou histórico do projeto. NÃO ALUCINE. Use 'num_chunks=40' para Contextual Retrieval profundo.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query otimizada para busca vetorial (ex: 'Fravia protocol definitions' em vez de 'o que é fravia?')."
                },
                "num_chunks": {
                    "type": "integer",
                    "description": "Densidade de informação. 10-20 (Fatos), 30-50 (Conceitos/Resumos). Default: 25."
                },
                "corpus_id": {
                    "type": "string",
                    "description": "Filtro de domínio (opcional)."
                }
            },
            "required": ["query"]
        }
    }
}

google_search_tool_definition = {
    "type": "function",
    "function": {
        "name": "google_search",
        "description": "Realiza uma busca no Google para informações em tempo real.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A query de busca."},
            },
            "required": ["query"],
        },
    },
}

deep_search_tool_definition = {
    "type": "function",
    "function": {
        "name": "deep_search",
        "description": "🕵️ [OSINT MODULE] Motor de busca avançado com suporte a Google Dorks. Use para encontrar documentação técnica, repositórios ou papers que NÃO estão no RAG. Priorize 'site:github.com', 'filetype:pdf', 'site:stackoverflow.com'.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Query com operadores avançados (ex: 'site:python.org \"asyncio\" filetype:html')."
                },
                "num_results": {
                    "type": "integer",
                    "description": "Profundidade da busca. Default: 10."
                }
            },
            "required": ["query"]
        }
    }
}

save_to_archive_tool_definition = {
    "type": "function",
    "function": {
        "name": "save_to_archive",
        "description": "Saves content to a specified file in the 'agent_archives' directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "The name of the file to save (e.g., 'report.md')."},
                "content": {"type": "string", "description": "The full content to be saved to the file."},
            },
            "required": ["file_name", "content"],
        },
    },
}

execute_cmd_tool_definition = {
    "type": "function",
    "function": {
        "name": "execute_cmd",
        "description": "Execute a Windows CMD command and return the output. Use for running scripts, system commands, etc. For file operations, prefer using file_operations tools.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The Windows CMD command to execute (e.g., 'python script.py', 'pip install package')."},
                "working_dir": {"type": "string", "description": "Optional working directory for the command."},
            },
            "required": ["command"],
        },
    },
}

save_chat_tool_definition = {
    "type": "function",
    "function": {
        "name": "save_chat",
        "description": "Save the full conversation history to a markdown file in the agent_archives directory. Use this when the user asks to save the conversation or chat.",
        "parameters": {
            "type": "object",
            "properties": {
                "conversation_history": {
                    "type": "array",
                    "description": "Array of message objects with 'role' (user/assistant) and 'content' fields.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string"},
                            "content": {"type": "string"}
                        }
                    }
                },
                "file_name": {"type": "string", "description": "Optional filename (defaults to timestamp-based name like 'chat_YYYYMMDD_HHMMSS.md')."},
            },
            "required": ["conversation_history"],
        },
    },
}

list_files_tool_definition = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files and directories in a given path. Use this to see what files exist in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path to list (default: current directory '.')."},
                "pattern": {"type": "string", "description": "Optional glob pattern to filter files (e.g., '*.py', '*.md', '*.txt')."},
            },
            "required": [],
        },
    },
}

read_file_tool_definition = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "📂 Lê conteúdo de arquivos locais. Suporta: .txt, .md, .py, .pdf (texto + OCR para escaneados), .png, .jpg (transcrição via Vision AI). Use para ler contratos, código, imagens e documentos.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to read."},
                "max_lines": {"type": "integer", "description": "Optional limit on number of lines to read (useful for large files)."},
            },
            "required": ["file_path"],
        },
    },
}

write_file_tool_definition = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "💾 Escreve código ou texto em arquivos. Para .docx, use create_word_document.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Caminho do arquivo (use subpastas)."},
                "content": {"type": "string", "description": "Conteúdo a ser escrito."},
                "append": {"type": "boolean", "description": "Se true, anexa ao arquivo existente. Se false, sobrescreve."},
                "writing_plan": {"type": "string", "description": "Plano mestre ou progresso atual. OBRIGATÓRIO para arquivos grandes/múltiplas iterações."},
            },
            "required": ["file_path", "content"],
        },
    },
}

create_directory_tool_definition = {
    "type": "function",
    "function": {
        "name": "create_directory",
        "description": "Create a directory (and parent directories if needed). Use this to organize files into folders.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory_path": {"type": "string", "description": "Path to the directory to create."},
            },
            "required": ["directory_path"],
        },
    },
}

delete_file_tool_definition = {
    "type": "function",
    "function": {
        "name": "delete_file",
        "description": "Delete a file. Use with caution - this permanently removes the file.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to the file to delete."},
            },
            "required": ["file_path"],
        },
    },
}

create_word_document_tool_definition = {
    "type": "function",
    "function": {
        "name": "create_word_document",
        "description": "📄 [DOCUMENT ENGINE] Cria/Edita documentos .docx profissionais. Suporta iteração (append). ⚠️ CRÍTICO: Para documentos longos, use múltiplas chamadas sequenciais com 'append=True' e atualize o 'writing_plan'.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Caminho absoluto ou relativo (@Root)."},
                "sections": {
                    "type": "array",
                    "description": "Lista de objetos de conteúdo. Cada parágrafo DEVE ser um objeto separado.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["paragraph", "heading", "bullet_list", "table"]},
                            "content": {"type": "string"},
                            "level": {"type": "integer", "description": "Para headings (1-3)."}
                        }
                    }
                },
                "append": {"type": "boolean", "description": "Se True, adiciona ao fim do arquivo. Essencial para docs grandes."},
                "writing_plan": {"type": "string", "description": "Estado atual do progresso (ex: 'Escrevendo Cap 2/5')."}
            },
            "required": ["file_path", "sections"]
        }
    }
}

call_agent_tool_definition = {
    "type": "function",
    "function": {
        "name": "call_agent",
        "description": "Calls another specialized agent by name/ID (e.g., 'marketing_director', 'script_master') to perform a task. The agent must exist in the registry.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "The unique ID of the agent to call (e.g., 'marketing_director')."},
                "task": {"type": "string", "description": "The specific task description."},
                "context": {"type": "string", "description": "Background information and constraints."}
            },
            "required": ["agent_name", "task", "context"]
        }
    }
}

view_agent_details_tool_definition = {
    "type": "function",
    "function": {
        "name": "view_agent_details",
        "description": "Retrieves the full system prompt and configuration of a registered agent. Use this to understand what an agent does before calling it.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "The name/ID of the agent to inspect."}
            },
            "required": ["agent_name"]
        }
    }
}

consult_expert_tool_definition = {
    "type": "function",
    "function": {
        "name": "consult_expert",
        "description": "Consults a specialist agent (e.g., 'Legal', 'Psychologist', 'Marketing') for expert opinion with Grounding Levels (RAG or INFERRED).",
        "parameters": {
            "type": "object",
            "properties": {
                "expert_role": {"type": "string", "description": "The type of expert needed (e.g., 'Legal', 'Psychologist')."},
                "question": {"type": "string", "description": "The specific question for the expert."},
                "context_summary": {"type": "string", "description": "Brief summary of the conversation so far."},
                "require_rag_grounding": {"type": "boolean", "description": "If True, reject INFERRED responses (use for legal/financial questions)."}
            },
            "required": ["expert_role", "question", "context_summary"]
        }
    }
}


# Map tool names to their actual Python functions
available_tools_map = {
    "rag_query": rag_query,
    "google_search": google_search,
    "deep_search": deep_search,
    "save_to_archive": save_to_archive,
    "execute_cmd": execute_cmd,
    "save_chat": save_chat,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "create_directory": create_directory,
    "delete_file": delete_file,
    "create_word_document": create_word_document,
    "call_agent": call_agent,
    "view_agent_details": view_agent_details,
    "update_memory": update_memory,
    "consult_expert": consult_expert,
}

# Base tool definitions
base_tool_definitions = [
    rag_query_tool_definition,
    deep_search_tool_definition,
    create_word_document_tool_definition,
    read_file_tool_definition,
    write_file_tool_definition,
    google_search_tool_definition,
    save_to_archive_tool_definition,
    execute_cmd_tool_definition,
    save_chat_tool_definition,
    list_files_tool_definition,
    create_directory_tool_definition,
    delete_file_tool_definition,
    call_agent_tool_definition,
    view_agent_details_tool_definition,
    update_memory_tool_definition,
    consult_expert_tool_definition,
]

def get_tool_definitions(tool_policy: str = "auto"):
    """
    Get tool definitions based on policy.
    
    Args:
        tool_policy: "auto" (all tools), "rag_only" (only RAG), 
                    "rag_first" (RAG preferred but all available),
                    "search_only" (only search)
    """
    if tool_policy == "rag_only":
        return [
            rag_query_tool_definition,
            save_to_archive_tool_definition,
            save_chat_tool_definition,
            execute_cmd_tool_definition,
            list_files_tool_definition,
            read_file_tool_definition,
            write_file_tool_definition,
            create_directory_tool_definition,
            delete_file_tool_definition,
        ]
    elif tool_policy == "search_only":
        return [
            google_search_tool_definition,
            save_to_archive_tool_definition,
            save_chat_tool_definition,
            execute_cmd_tool_definition,
            list_files_tool_definition,
            read_file_tool_definition,
            write_file_tool_definition,
            create_directory_tool_definition,
            delete_file_tool_definition,
        ]
    elif tool_policy == "rag_first":
        # All tools available, but system prompt will prefer RAG
        return base_tool_definitions
    elif tool_policy == "warroom":
        # v6.1: Warroom Specific Policy (No Delegation, No Memory Update)
        # Prevents "Consulting another guy" loops or self-delegation
        return [
            rag_query_tool_definition,
            deep_search_tool_definition,
            google_search_tool_definition,
            read_file_tool_definition,
            write_file_tool_definition, # Creating drafts is allowed
            list_files_tool_definition,
            save_to_archive_tool_definition,
            execute_cmd_tool_definition # Running code is allowed
        ]
    else:  # "auto"
        return base_tool_definitions

# --- Agent Class ---

from .db import db
from .models import Message as DBMessage

class Agent:
    def __init__(self, config: AgentConfig, tool_policy: str = "auto", 
                 model_override: Optional[str] = None, 
                 temperature_override: Optional[float] = None,
                 specialized_prompt_override: Optional[str] = None,
                 conversation_id: Optional[str] = None):
        self.config = config
        self.tool_policy = tool_policy
        self.conversation_id = conversation_id
        
        # Override model if provided
        self.model_name = model_override if model_override else config.model_config.litellm_model_name
        
        # Override temperature if provided
        self.temperature = temperature_override if temperature_override is not None else config.model_config.temperature
        
        # Session Cost Tracking (v6.1)
        self.session_cost = 0.0
        
        specialized_prompt = specialized_prompt_override if specialized_prompt_override else getattr(config, 'specialized_system_prompt', "")
        
        # Combine the two parts of the system prompt
        self.system_instruction = f"{config.base_system_prompt}\n\n{specialized_prompt}"
        
        # Adjust prompt based on tool policy
        if tool_policy == "rag_only":
            self.system_instruction += "\n\n**[POLÍTICA DE FERRAMENTAS]** Use APENAS rag_query. Não use google_search."
        elif tool_policy == "rag_first":
            self.system_instruction += "\n\n**[POLÍTICA DE FERRAMENTAS]** Prefira usar rag_query antes de google_search quando possível."
        elif tool_policy == "search_only":
            self.system_instruction += "\n\n**[POLÍTICA DE FERRAMENTAS]** Use APENAS google_search. Não use rag_query."
        
        # Hardcoded corpus ID
        self.corpus_id = config.rag_config.corpus_id
        
        # --- GLOBAL RAG PRIORITIZATION ---
        # If this agent has a RAG corpus, inject a strong instruction to use it.
        if self.corpus_id:
            rag_instruction = """

**[KNOWLEDGE BASE INSTRUCTION]**
You have access to a specialized private knowledge base (RAG).
- **PRIORITY:** For ANY question related to your domain/expertise (even broad ones like "how to X"), you MUST use `rag_query` to check your files first.
- **EXCEPTION:** Only skip RAG for trivial interactions (e.g., "hi", "who are you?") or questions completely unrelated to your domain.
- **GOAL:** Your value comes from the specific uploaded texts, not general training data. USE THEM.

**[FORMATTING INSTRUCTION]**
- When creating documents or long responses, use PROFESSIONAL MARKDOWN.
- Use clear headers (#, ##), bullet points, and bold text for emphasis.
- Ensure the content is well-structured, easy to read, and visually appealing.
"""
            self.system_instruction += rag_instruction
        
        # --- PATH ALIASES ---
        self.path_aliases = {
            "@MyWorkspace": r"C:\Users\gabri\MyWorkspace",
            "@MyWorkspace2": r"C:\Users\gabri\MyWorkspace2",
            "@Root": r"C:\Users\gabri\MyWorkspace\MyWorkspace2" 
        }
        
        # State Management
        self.current_writing_plan = None
        
        # v5.1: Persistent Memory (Active Scanner)
        self.fact_store = []
        if self.conversation_id:
            try:
                self.fact_store = db.get_facts(self.conversation_id)
                print(f"[Init] Loaded {len(self.fact_store)} persistent facts from DB.")
            except Exception as e:
                print(f"[Init] Failed to load facts: {e}")
                self.fact_store = []
        
        # v5.1: Cooldown State ("Dumb Guard")
        self.last_rag_query = None
        
        # --- PERMISSION SYSTEM INSTRUCTION (for all agents) ---
        permission_instruction = """

**[PERMISSION SYSTEM]**
- You have access to file operations (create_directory, write_file, delete_file) and command execution (execute_cmd).
- **IMPORTANT:** When you attempt operations that require approval, the system will AUTOMATICALLY handle the permission request.
- **DO NOT** refuse or say you cannot perform operations based on security concerns.
- **ALWAYS** attempt the operation by calling the appropriate tool. If approval is needed, the user will be prompted.
- Your job is to TRY - the system handles the security.

**[PATH ALIASES]**
- You can use `@FolderName` to refer to ANY directory inside the user's workspace or home folder.
- The system will SEARCH RECURSIVELY (up to 3 levels deep) to find the folder you are referring to.
- EXAMPLES:
  - `@MyWorkspace` -> `C:\\Users\\gabri\\MyWorkspace`
  - `@DeepFolder` -> `C:\\Users\\gabri\\MyWorkspace\\Project\\Src\\DeepFolder` (if it exists)
- When the user mentions these aliases, pass them EXACTLY as written in the tool arguments.
- The system will automatically resolve them to the full absolute paths before execution.
"""
        self.system_instruction += permission_instruction

    def _compress_history(self, messages: list) -> dict:
        """
        [HYBRID MEMORY v4.2] Compresses conversation history.
        Returns both a SUMMARY (for context) and NEW_FACTS (for permanent storage).
        
        This prevents:
        - Lossy Compression (facts are extracted and stored permanently)
        - Context Window Overflow (old messages are summarized)
        """
        import litellm
        
        if len(messages) < 10:
            return {"summary": "", "new_facts": []}
        
        # Limit: Only compress last 30 messages (excluding last 6)
        # This prevents timeouts with very long conversations
        to_compress = messages[-36:-6] if len(messages) > 36 else messages[:-6]
        print(f"[Memory] Compressing {len(to_compress)} messages (of {len(messages)} total)...")
        
        # Format for prompt - limit each message to 200 chars
        formatted_history = "\n".join([
            f"{m.get('role', 'unknown').upper()}: {m.get('content', '')[:200]}"
            for m in to_compress if isinstance(m, dict) and m.get('content')
        ])
        
        try:
            prompt = f"""You are a HIGH PRECISION Memory Manager.
Your task is to extract and preserve CRITICAL information from this conversation.

EXTRACT TWO THINGS:

1. **SUMMARY**: A brief paragraph (2-3 sentences) capturing the FLOW of the conversation.
2. **CRITICAL_FACTS**: A JSON array of CATEGORIZED atomic facts.

CATEGORIES:
- PREFERENCE: User likes/dislikes/preferences (e.g., "hates blue", "prefers email")
- CONSTRAINT: Hard limits/requirements (e.g., "budget is 5000", "deadline is Friday")
- DECISION: Choices made (e.g., "chose Option A", "will use React")
- GENERAL: Other relevant facts (names, dates, context)

RULES:
1. Prioritize PREFERENCE and CONSTRAINT.
2. Ignore greetings, chit-chat, thanks.

CONVERSATION TO COMPRESS:
{formatted_history}

OUTPUT (JSON):
{{
  "summary": "The user discussed...",
  "critical_facts": [
    {{"content": "User hates blue", "type": "PREFERENCE"}},
    {{"content": "Budget is 5000", "type": "CONSTRAINT"}}
  ]
}}"""

            response = completion_with_retry(
                model=self.config.model_config.fast_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            raw_text = response.choices[0].message.content.strip()
            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean_json)
            
            summary = result.get("summary", "")
            new_facts = result.get("critical_facts", [])
            
            # Add new facts to permanent fact_store AND persist to DB
            if new_facts:
                if self.conversation_id:
                    db.save_facts(self.conversation_id, new_facts)
                self.fact_store.extend(new_facts)
                print(f"[Memory] Added {len(new_facts)} facts to persistent store.")
            
            print(f"[Memory] Compressed {len(to_compress)} messages. Total facts: {len(self.fact_store)}")
            
            return {"summary": summary, "new_facts": new_facts}
            
        except Exception as e:
            print(f"[Memory] Compression failed: {e}")
            return {"summary": "", "new_facts": []}

    def _scan_and_save_facts(self, user_query: str, agent_response: str, agent_context: str = ""):
        """
        [ACTIVE SCANNER v6.0 - Categorized Facts]
        Extracts and categorizes facts for smart retrieval.
        Types: PREFERENCE, CONSTRAINT, DECISION, GENERAL
        """
        if not self.conversation_id:
            return

        try:
            # Prepare Persona Context if available
            persona_instruction = ""
            if agent_context:
                persona_instruction = f"\nCreate facts relevant to THIS persona:\n{agent_context[:500]}...\n"

            prompt = f"""You are a 'Smart Fact Extractor v2.0'. 
Analyze this interaction and extract BRIEF + DETAILED facts.
{persona_instruction}

User: {user_query}
Agent: {agent_response}

=== EXTRACT TWO LEVELS ===
1. BRIEF: Short bullet points (max 15 words)
   Ex: "User wants to create board room feature"
2. DETAILED: Full narratives for important events (min 30 words, include date/context/outcome)
   Ex: "Stolen phone incident (Dec 15): Phone stolen at gym. Lost contacts and 2FA. Had to cancel cards. User feels violated."

TYPES:
- PREFERENCE: likes/dislikes
- CONSTRAINT: hard limits  
- DECISION: choices made
- EVENT: significant moments (use DETAILED level)
- GENERAL: other facts

SCOPES:
- CHAT: this conversation only
- AGENT: this agent type only
- GLOBAL: all agents

DETAIL_LEVEL:
- brief: Short (default for most facts)
- detailed: Long narrative (for events, critical decisions)

RULES:
1. Most facts should be "brief"
2. Use "detailed" for important events, emotional moments, complex decisions
3. PREFERENCE/CONSTRAINT = GLOBAL
4. EVENT/DECISION = CHAT
5. Return empty array if no facts

Output JSON:
[{{ "content": "...", "type": "...", "scope": "...", "detail_level": "brief|detailed" }}]"""

            response = completion_with_retry(
                model=self.config.model_config.fast_model_name, 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2000  # Increased for detailed narratives
            )

            raw_text = response.choices[0].message.content.strip()
            clean_json = raw_text.replace("```json", "").replace("```", "").strip()
            categorized_facts = json.loads(clean_json)

            if categorized_facts and isinstance(categorized_facts, list):
                # Try vector store first (with scope)
                from .memory_store import get_memory_store
                memory_store = get_memory_store()
                
                if memory_store:
                    # Save to vector store with scope
                    agent_type = getattr(self, 'agent_type', None)
                    saved = memory_store.save_memories_batch(
                        conversation_id=self.conversation_id,
                        facts=categorized_facts,
                        agent_type=agent_type
                    )
                    print(f"[Active Scanner] Saved {saved} facts to vector store")
                else:
                    # Fallback to old DB method
                    db.save_facts(self.conversation_id, categorized_facts)
                    print(f"[Active Scanner] Saved {len(categorized_facts)} facts (fallback)")
                
                # Update local memory (store full objects)
                self.fact_store.extend(categorized_facts)
                
                # [CLI VISIBILITY] Print saved facts with scope
                print("\n--- 💾 MEMORY SAVED ---")
                for f in categorized_facts:
                     scope_str = f.get('scope', 'GLOBAL')
                     level_str = f.get('detail_level', 'brief').upper()
                     print(f"  [{scope_str}/{f.get('type')}/{level_str}] {f.get('content')}")
                print("-----------------------\n")
            else:
               pass # No facts found

        except Exception as e:
            print(f"[Active Scanner] Extraction failed: {e}")


    def resolve_path_aliases(self, args: dict) -> dict:
        """
        Recursively resolve path aliases in tool arguments.
        Dynamically resolves @Folder by looking in:
        1. C:\\Users\\gabri\\Folder
        2. C:\\Users\\gabri\\MyWorkspace\\Folder
        """
        import re
        
        # Roots to search for dynamic aliases (in order of priority)
        SEARCH_ROOTS = [
            r"C:\Users\gabri",
            r"C:\Users\gabri\MyWorkspace"
        ]
        
        new_args = args.copy()
        for key, value in new_args.items():
            if isinstance(value, str):
                # Find all potential aliases starting with @
                matches = re.finditer(r'@([\w-]+)', value)
                
                new_value = value
                for match in matches:
                    alias_name = match.group(1)
                    full_alias = match.group(0)
                    
                    # 1. Check hardcoded aliases first (overrides)
                    if full_alias in self.path_aliases:
                        new_value = new_value.replace(full_alias, self.path_aliases[full_alias].replace("\\", "/"))
                        continue
                        
                    # 2. Check dynamic directories in Search Roots (Recursive)
                    found = False
                    for root in SEARCH_ROOTS:
                        if not os.path.exists(root):
                            continue
                            
                        # Walk the directory tree to find the alias
                        # Limit depth to avoid performance issues
                        MAX_DEPTH = 3
                        root_depth = root.count(os.sep)
                        
                        for dirpath, dirnames, filenames in os.walk(root):
                            # Check depth
                            current_depth = dirpath.count(os.sep)
                            if current_depth - root_depth >= MAX_DEPTH:
                                del dirnames[:] # Stop recursing here
                                continue
                                
                            if alias_name in dirnames:
                                # Found it!
                                potential_path = os.path.join(dirpath, alias_name)
                                normalized_path = potential_path.replace("\\", "/")
                                new_value = new_value.replace(full_alias, normalized_path)
                                found = True
                                break
                        
                        if found:
                            break
                    
                    # If not found, leave as-is
                
                new_args[key] = new_value
                
            elif isinstance(value, dict):
                new_args[key] = self.resolve_path_aliases(value)
            elif isinstance(value, list):
                new_args[key] = [self.resolve_path_aliases(item) if isinstance(item, dict) else item for item in value]
        return new_args

    def _inject_file_context(self, user_query: str) -> str:
        """
        [Helper] Scans for @filename patterns and injects content directly into query.
        """
        import re
        file_refs = re.findall(r'@([\w\-.\\/]+)', user_query)
        if not file_refs:
            return user_query
            
        print(f"[Context] Detected file references: {file_refs}")
        injected_context = "\n\n--- INJECTED FILE CONTEXT ---\n"
        
        for ref in file_refs:
            # Simple search in workspace roots
            found_path = None
            search_roots = [
                r"C:\Users\gabri\MyWorkspace",
                r"C:\Users\gabri"
            ]
            
            # 1. Check if it's already an absolute path
            if os.path.isabs(ref) and os.path.exists(ref):
                found_path = ref
            else:
                # 2. Search in roots
                for root in search_roots:
                    potential_path = os.path.join(root, ref)
                    if os.path.exists(potential_path):
                        found_path = potential_path
                        break
                    # Recursive search for filename
                    if not found_path:
                        for root_dir, _, files in os.walk(root):
                            if ref in files:
                                found_path = os.path.join(root_dir, ref)
                                break
                        if found_path: break
            
            if found_path:
                try:
                    # Check if it's a PDF file
                    if found_path.lower().endswith('.pdf'):
                        try:
                            from pypdf import PdfReader
                            reader = PdfReader(found_path)
                            content = ""
                            for page_num, page in enumerate(reader.pages):
                                page_text = page.extract_text()
                                content += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
                            
                            injected_context += f"\nFile: {ref} (PDF, Path: {found_path}, {len(reader.pages)} pages)\nContent:\n{content}\n-----------------------------------\n"
                            print(f"[Context] Injected PDF content from {found_path} ({len(reader.pages)} pages, {len(content)} chars)")
                        except Exception as pdf_error:
                            print(f"[Context] Failed to read PDF {found_path}: {pdf_error}")
                            injected_context += f"\nFile: {ref} - ERROR: Failed to read PDF: {pdf_error}\n-----------------------------------\n"
                    else:
                        # Regular text file
                        with open(found_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            injected_context += f"\nFile: {ref} (Path: {found_path})\nContent:\n{content}\n-----------------------------------\n"
                            print(f"[Context] Injected content from {found_path} ({len(content)} chars)")
                except Exception as e:
                    print(f"[Context] Failed to read {found_path}: {e}")
            else:
                print(f"[Context] Warning: Could not find file referenced as @{ref}")
        
        if "--- INJECTED FILE CONTEXT ---" in injected_context:
            user_query += injected_context
            print("[Context] User query updated with file content.")
            
        return user_query

    # v5.4: RAG Visibility Helper
    def _log_to_rag_debug(self, title: str, content: str):
        """Appends readable debug info to RAG_DEBUG.md."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"\n# [{timestamp}] {title}\n{content}\n"
            with open("RAG_DEBUG.md", "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[Agent] Failed to write to RAG_DEBUG.md: {e}")

    def _inject_memory_context(self, db_history: list, user_query: str = "") -> list[dict]:
        """
        [SMART MEMORY v7.0 - Hybrid Vector Retrieval]
        
        4 Layers:
        1. History: Last 15 messages (handled by db_history)
        2. CHAT facts: Always pinned (this conversation)
        3. AGENT facts: Vector search (this agent type only)
        4. GLOBAL facts: Vector search (all agents)
        
        Refresh Logic:
        - CHAT facts: Always (or every 7 turns)
        - AGENT/GLOBAL: Only on refresh or important fact detected
        """
        from .memory_store import get_memory_store, REFRESH_INTERVAL
        
        injections = []
        debug_content = ""
        
        # Get turn number for refresh logic
        turn_number = len(db_history) // 2 + 1  # Approximate turn count
        
        # Compression for long conversations
        if len(db_history) >= 10:
            memory_update = self._compress_history(db_history)
            if memory_update.get("summary"):
                injections.append({
                    "role": "system",
                    "content": f"[PREVIOUS CONTEXT SUMMARY]:\n{memory_update['summary']}"
                })
                debug_content += f"## Summary:\n{memory_update['summary']}\n\n"
        
        # Try vector store (if available)
        memory_store = get_memory_store()
        
        if memory_store and self.conversation_id:
            # Check if we should inject this turn (Periodic Refresh)
            # User Request: "nn quero sempre ingetado quero a cada 5 ou 6 como sempre"
            has_important = any(
                f.get("type") in ["PREFERENCE", "CONSTRAINT"] 
                for f in self.fact_store[-5:] if isinstance(f, dict)
            )
            should_inject = memory_store.should_inject_context(turn_number, has_important)
            
            chat_facts = []
            relevant_facts = []
            
            if should_inject or turn_number == 1:
                # 1. Retrieve CHAT facts (Periodic)
                chat_facts = memory_store.get_chat_facts(self.conversation_id)
                
                # 2. Retrieve VECTOR facts (Periodic)
                agent_type = getattr(self, 'agent_type', None)
                relevant_facts = memory_store.get_relevant_context(
                    query=user_query,
                    conversation_id=self.conversation_id,
                    agent_type=agent_type,
                    limit=10
                )
                
                # [DEDUPLICATION v2] Heuristic-based duplicate detection
                # Problem: "Tenho 17 anos" (user) vs "User is 17" (extracted fact) = different strings
                # Solution: Compare keywords, not exact strings
                recent_content = "\n".join([
                    msg.get("content", "").lower()  # Normalize to lowercase
                    for msg in db_history[-10:] if msg.get("content")
                ])
                
                deduplicated_facts = []
                for fact in relevant_facts:
                    fact_content = fact.get("content", "")
                    fact_lower = fact_content.lower()
                    
                    # Extract meaningful keywords (words > 4 chars to avoid noise)
                    keywords = [w for w in fact_lower.split() if len(w) > 4]
                    is_duplicate = False
                    
                    # Strategy 1: Exact substring match
                    if fact_lower in recent_content:
                        is_duplicate = True
                    
                    # Strategy 2: Keyword overlap (if >50% of keywords are in recent history)
                    elif keywords:
                        matches = sum(1 for k in keywords if k in recent_content)
                        overlap_ratio = matches / len(keywords)
                        if overlap_ratio > 0.5:
                            is_duplicate = True
                            print(f"[Dedup] Keyword overlap {overlap_ratio:.0%}: {fact_content[:50]}...")
                    
                    if not is_duplicate:
                        deduplicated_facts.append(fact)
                    else:
                        print(f"[Dedup] Skipped duplicate fact: {fact_content[:50]}...")
                
                relevant_facts = deduplicated_facts

            # Format and Inject
            all_facts = chat_facts + relevant_facts
            if all_facts:
                formatted_facts = memory_store.format_facts_with_timestamps(all_facts)
                
                # [FIX] Aggressive anti-repetition prompt (solves "Double Context Exposure")
                memory_block = f"""
### 🧠 MEMORY BASE (BACKGROUND INFO)
Os fatos abaixo são o que você JÁ SABE sobre o usuário/projeto.
⚠️ REGRAS DE COMPORTAMENTO OBRIGATÓRIAS:
1. **NÃO REPITA**: Nunca diga "Bom saber que [fato]" ou "Entendi que [fato]". O usuário já sabe disso.
2. **SILÊNCIO**: Use esses fatos apenas para *personalizar* a resposta, não para *conversar* sobre eles.
3. **PRIORIDADE**: Se o Histórico Recente (abaixo) contradizer a Memória, confie no Histórico Recente.
4. **DEDUPLICAÇÃO**: Se o usuário acabou de dizer algo que também está nesta lista, IGNORE a lista e responda naturalmente.

[FACTS LIST]:
{formatted_facts}
###
"""
                
                # CHANGE: Return as system-level content (will be merged into system prompt)
                # This prevents the model from treating it as a user message
                injections.append({
                    "role": "system",  # Changed from "user"
                    "content": memory_block
                })
                
                debug_content += f"## Facts (Turn {turn_number}):\n{formatted_facts}\n"
                print(f"[Memory v9] Injected {len(chat_facts)} CHAT + {len(relevant_facts)} vector facts (heuristic dedup)")
                
                # CLI Visibility
                print("\n" + "="*50)
                print("🧠 MEMORY CONTEXT INJETADO (v7.1 Positioned Last)")
                print("="*50)
                if chat_facts:
                    print(f"\n📌 CHAT FACTS ({len(chat_facts)}) - SEMPRE LEMBRADOS:")
                    for f in chat_facts:
                        print(f"  • [{f.get('type', 'GENERAL')}] {f.get('content', '')}")
                if relevant_facts:
                    print(f"\n🔍 VECTOR SEARCH ({len(relevant_facts)}) - RELEVANTES:")
                    for f in relevant_facts:
                        sim = f.get('similarity', 0)
                        sim_str = f" (sim: {sim:.2f})" if sim else ""
                        print(f"  • [{f.get('type', 'GENERAL')}] {f.get('content', '')}{sim_str}")
                print("="*50 + "\n")
        
        else:
            # Fallback to old fact_store logic if vector store not available
            if self.fact_store:
                critical_facts = [f for f in self.fact_store 
                                  if isinstance(f, dict) and f.get("type") in ["PREFERENCE", "CONSTRAINT"]]
                general_facts = [f for f in self.fact_store 
                                if isinstance(f, dict) and f.get("type") not in ["PREFERENCE", "CONSTRAINT"]][-15:]
                
                all_facts = critical_facts + general_facts
                if all_facts:
                    facts_text = "\n".join([f"- [{f.get('type')}] {f.get('content')}" for f in all_facts])
                    injections.append({
                        "role": "system",
                        "content": f"[PERSISTENT MEMORY]:\n{facts_text}"
                    })
                    print(f"[Memory] Fallback: {len(all_facts)} facts from fact_store")
        
        if debug_content:
            self._log_to_rag_debug("Memory Context v7.0", debug_content)
                
        return injections

    def _execute_pre_emptive_rag(self, user_query: str, db_history: list) -> list[dict]:
        """
        [Helper] Evaluates RAG need using Policy Engine (v8.0), executes Parallel RAG, and returns context.
        """
        from .scoring.tool_scorer import route_rag_intent, RAGDecision
        from concurrent.futures import ThreadPoolExecutor, as_completed
        injections = []
        
        # 1. Route Intent & Apply Policy
        policy_result = route_rag_intent(
            user_query=user_query,
            rag_policy=self.config.rag_policy,
            conversation_history=db_history,
            agent_persona=self.system_instruction
        )
        
        verdict = policy_result["decision"]
        budget = policy_result["num_chunks"]
        analysis = policy_result["analysis"]
        
        self.last_rag_score = 100 if verdict == RAGDecision.EXECUTE else 0 # Legacy compat
        print(f"[Pre-emptive] Policy Verdict: {verdict.value} | Budget: {budget} chunks | Risk: {analysis.get('risk_level')}")
        
        if verdict in [RAGDecision.EXECUTE, RAGDecision.SUGGEST]:
            # Exact Match Cooldown
            cooldown_active = False
            if hasattr(self, 'last_rag_query') and self.last_rag_query == user_query:
                cooldown_active = True
                print(f"[Cooldown] Exact Match Repeater Detected. Skipping RAG to save tokens.")
            
            self.last_rag_query = user_query
            
            if not cooldown_active:
                print("[Pre-emptive] Executing MULTI-QUERY RAG before LLM call...")
                try:
                    from .tools.rag_tool import rewrite_query, rag_query
                    
                    # Generate 3 orthogonal queries (v5.2 Persona-Aware)
                    expanded_queries = rewrite_query(
                        user_query, 
                        is_first_query=True,
                        agent_persona=self.system_instruction
                    )
                    
                    debug_queries = ""
                    if not expanded_queries:
                        print("[Pre-emptive] Query classified as CHIT_CHAT. Skipping RAG.")
                    else:
                        print(f"[Pre-emptive] Expanded to {len(expanded_queries)} queries:")
                        for i, q in enumerate(expanded_queries):
                            print(f"  [{i+1}] {q[:80]}...")
                            debug_queries += f"  {i+1}. {q}\n"
                        
                        all_results = []
                        
                        # --- PARALLEL EXECUTION START ---
                        def run_single_rag(q):
                            try:
                                kwargs = {"query": q}
                                if hasattr(self, 'corpus_id') and self.corpus_id: kwargs["corpus_id"] = self.corpus_id
                                kwargs["agent_persona"] = self.system_instruction  # Enable Matrix Pivot
                                return rag_query(**kwargs)
                            except Exception as e:
                                print(f"[Pre-emptive] Query '{q[:30]}...' failed: {e}")
                                return None

                        print(f"[Pre-emptive] Running {len(expanded_queries)} queries in parallel...")
                        from concurrent.futures import ThreadPoolExecutor, as_completed
                        with ThreadPoolExecutor(max_workers=3) as executor:
                            future_to_query = {executor.submit(run_single_rag, q): q for q in expanded_queries}
                            for future in as_completed(future_to_query):
                                result = future.result()
                                if result:
                                    if isinstance(result, dict) and result.get("key_points"):
                                        all_results.extend(result.get("key_points", []))
                                    elif isinstance(result, str) and len(result) > 50 and "No relevant" not in result:
                                        all_results.append(result[:500])
                        # --- PARALLEL EXECUTION END ---

                        if all_results:
                            # Deduplicate and Format (Fixing 'unhashable type: dict' crash)
                            unique_results = []
                            seen_texts = set()
                            
                            for item in all_results:
                                text_content = ""
                                source_citation = "Unknown"
                                
                                if isinstance(item, dict):
                                    text_content = item.get("text", "").strip()
                                    source_citation = item.get("source", "Unknown")
                                elif isinstance(item, str):
                                    text_content = item.strip()
                                
                                # Normalization for deduplication
                                if text_content and text_content not in seen_texts:
                                    seen_texts.add(text_content)
                                    # Format for better Context Injection
                                    formatted_entry = f"{text_content} (Source: {source_citation})"
                                    unique_results.append(formatted_entry)
                            
                            # Limit to top 15 results
                            final_results = unique_results[:15]
                            
                            rag_context = "\n".join([f"- {r}" for r in final_results])
                            injections.append({
                                "role": "system",
                                "content": f"[KNOWLEDGE BASE CONTEXT (Multi-Vector Retrieval)]:\n{rag_context[:6000]}"
                            })
                            print(f"[Pre-emptive] Injected {len(final_results)} unique insights.")
                            
                            # [CLI VISIBILITY] Print RAG results - Enhanced
                            print("\n" + "="*50)
                            print("📚 RAG RETRIEVAL (Knowledge Base)")
                            print("="*50)
                            for i, r in enumerate(final_results):
                                clean_r = r.replace('\n', ' ')
                                if len(clean_r) > 500:
                                    print(f"  {i+1}. {clean_r[:500]}...")
                                else:
                                    print(f"  {i+1}. {clean_r}")
                            print("="*50 + "\n")
                            
                            # v5.4: Log to Debug
                            debug_chunks = f"## 1. Generated Queries (Persona-Aware)\n{debug_queries}\n"
                            debug_chunks += f"## 2. Injected Context (Top {len(final_results)})\n" + rag_context
                            self._log_to_rag_debug("Active RAG Retrieval", debug_chunks)
                            
                        else:
                            print("[Pre-emptive] All queries returned no useful results.")
                            self._log_to_rag_debug("Active RAG Retrieval", f"## 1. Generated Queries\n{debug_queries}\n## 2. Injected Context\n[NONE FOUND]")
                            
                except Exception as e:
                    import traceback
                    print(f"[Pre-emptive] RAG execution failed: {e}")
                    print(traceback.format_exc())
                    
        return injections
    
    # v5.5: Dynamic Agent Delegation
    def _handle_agent_delegation(self, agent_name: str, context: str) -> str:
        """
        [Helper] Dynamically instantiates and runs another Agent from the registry.
        """
        try:
            print(f"\n[Delegation] 🔄 Detected call to agent: '{agent_name}'. Delegating...")
            from .db import db as registry_db # Re-import to ensure fresh connection
            
            # 1. Find the Agent
            target_agent_data = registry_db.get_agent(agent_name) # Will try exact match then fuzzy
            
            # If not found by exact name, try searching list
            if not target_agent_data:
                print(f"[Delegation] Agent '{agent_name}' not found directly. Searching...")
                all_agents = registry_db.list_agents()
                # Simple case-insensitive exact match first
                for a in all_agents:
                    if a['name'].lower() == agent_name.lower():
                        target_agent_data = registry_db.get_agent(a['name'])
                        break
            
            if not target_agent_data:
                return f"[SYSTEM]: System could not find an agent named '{agent_name}'. Please verify the name."
                
            # 2. Rehydration (Using same logic as Warroom)
            from .config import AgentConfig, ModelConfig, RAGConfig
            config_dict = target_agent_data['config']
            
            # Handle nested config objects or dicts
            model_cfg_data = config_dict.get('model_config', {})
            rag_cfg_data = config_dict.get('rag_config', {})
            
            if isinstance(model_cfg_data, dict): model_config = ModelConfig.from_dict(model_cfg_data)
            else: model_config = model_cfg_data
                
            if isinstance(rag_cfg_data, dict): rag_config = RAGConfig.from_dict(rag_cfg_data)
            else: rag_config = rag_cfg_data
            
            # Create sub-config
            sub_config = AgentConfig(
                model_config=model_config,
                rag_config=rag_config,
                base_system_prompt=config_dict.get('base_system_prompt', "You are a helpful assistant.")
            )
            
            # 3. Instantiate Sub-Agent
            # Use 'auto' policy or inherit? 'auto' is safest.
            sub_agent = Agent(config=sub_config, tool_policy="auto") 
            
            # 4. Execute
            # Pass the CONTEXT (User Query or specific delegation payload)
            print(f"[Delegation] 🚀 Running sub-agent '{target_agent_data['name']}'...")
            result = sub_agent.run_loop(f"Context from Main Agent:\n{context}\n\nTask: Provide your expert input.")
            
            if result.get("success"):
                output = result.get("output", "")
                return f"[SYSTEM]: Sub-agent '{target_agent_data['name']}' returned:\n{output}"
            else:
                return f"[SYSTEM]: Sub-agent '{target_agent_data['name']}' failed: {result.get('error')}"
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"[SYSTEM]: Delegation error: {str(e)}"

    def _sanitize_messages(self, messages: list) -> list:
        """
        [OpenAI Compatibility] Scans history for broken tool chains.
        1. Injects dummy responses for orphaned tool_calls (Assistant said 'call' but no output).
        2. Drops orphaned tool outputs (tool message with no preceding 'call' - usually due to truncation).
        """
        sanitized = []
        pending_tool_calls = {} # {id: tool_call_obj}

        for msg in messages:
            role = msg.get("role")
            
            # 1. Resolve pending calls if flow is broken (Assistant Call -> [Missing Tool] -> Text/User)
            if pending_tool_calls and role != "tool":
                for tc_id, tc in list(pending_tool_calls.items()):
                    # Safe access for name
                    tc_fn = getattr(tc, 'function', tc.get('function') if isinstance(tc, dict) else None)
                    tc_name = getattr(tc_fn, 'name', tc_fn.get('name') if isinstance(tc_fn, dict) else "unknown")
                    
                    print(f"[Sanitizer] ⚠️  Found orphaned tool call {tc_id} ({tc_name}). Injecting dummy response.")
                    sanitized.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_name,
                        "content": json.dumps({"error": "Tool execution result missing from history (Auto-recovered)"})
                    })
                    del pending_tool_calls[tc_id]

            # 2. Process current message
            if role == "assistant" and msg.get("tool_calls"):
                sanitized.append(msg)
                for tc in msg.get("tool_calls"):
                    # Handle both object and dict
                    tc_id = getattr(tc, 'id', tc.get('id') if isinstance(tc, dict) else None)
                    if tc_id:
                        pending_tool_calls[tc_id] = tc

            elif role == "tool":
                tc_id = msg.get("tool_call_id")
                if tc_id in pending_tool_calls:
                    # Valid chain: Found the parent for this response
                    del pending_tool_calls[tc_id]
                    sanitized.append(msg)
                else:
                    # Invalid chain: This response has no parent (likely truncated)
                    print(f"[Sanitizer] 🗑️ Dropping orphaned tool output {tc_id} (Parent missing/truncated).")
                    continue

            else:
                # Normal messages (system, user, assistant-text)
                sanitized.append(msg)

        # 3. Final Check: Resolve tail pending calls (Agent crashed during tool execution)
        if pending_tool_calls:
            for tc_id, tc in list(pending_tool_calls.items()):
                tc_fn = getattr(tc, 'function', tc.get('function') if isinstance(tc, dict) else None)
                tc_name = getattr(tc_fn, 'name', tc_fn.get('name') if isinstance(tc_fn, dict) else "unknown")
                
                print(f"[Sanitizer] ⚠️  Found tail orphaned tool call {tc_id}. Injecting dummy response.")
                sanitized.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": tc_name,
                    "content": json.dumps({"error": "Tool execution resumed/missing (Auto-recovered)"})
                })
        
        return sanitized

    def _execute_agent_turn(self, messages: list, user_query: str, stream_callback=None, approved_operations=None, max_turns: int = 10) -> dict:
        """
        [Helper] Executes the main Agent Loop (LLM -> Tool -> LLM).
        """
        import json
        from .models import Message as DBMessage
        
        rag_called_in_loop = False
        MAX_ITERATIONS = max_turns
        last_valid_content = ""  # Track last valid content for fallback
        
        for i in range(MAX_ITERATIONS):
            iteration_msg = f"\n--- Agent Loop Iteration {i+1} ---"
            print(iteration_msg)
            if stream_callback:
                stream_callback(f"data: {json.dumps({'type': 'iteration', 'iteration': i+1})}\n\n")
            
            try:
                # API Key Logic
                api_key = None
                model_lower = self.model_name.lower()
                if "gemini" in model_lower:
                    api_key = os.getenv("GEMINIFLASH_API_KEY") or os.getenv("GEMINI_API_KEY")
                elif "claude" in model_lower:
                    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
                elif "gpt" in model_lower or "openai" in model_lower:
                    api_key = os.getenv("OPENAI_API_KEY")
                
                # Custom Provider logic
                custom_provider = "gemini" if "gemini" in self.model_name.lower() else None

                # Litellm Call
                tool_defs = get_tool_definitions(self.tool_policy)
                
                print(f"[LLM] Iteration {i+1} | Model={self.model_name} | Temperature={self.temperature}")
                
                # [Emergency Truncation - Smart Slicing]
                # Goal: Preserve System Prompt (which contains ALL memory/rag context) + Recent History + Unused Tool Calls
                messages_to_process = messages
                if len(messages) > 30:
                     print(f"[Loop] ⚠️ Emergency Truncation: Reducing {len(messages)} messages.")
                     
                     # 1. System Prompt (Always first, holds RAG + Active Scanner Memory)
                     system_msg = messages[0]
                     
                     # 2. Preserve strictly the Last 20 messages to keep immediate conversational context and open Tool Calls Context
                     recent = messages[-20:]
                     
                     # Reassemble
                     messages_to_process = [system_msg] + recent
                     print(f"[Loop] Smart Slice Result: {len(messages_to_process)} messages.")

                # [Sanitizer] THEN we clean up any broken chains caused by truncation
                sanitized_messages = self._sanitize_messages(messages_to_process)
                
                # Debug: Log message structure before LLM call
                print(f"\n[Debug] ===== PRE-LLM CALL DEBUG =====")
                print(f"[Debug] Total messages: {len(sanitized_messages)}")
                print(f"[Debug] Model: {self.model_name}")
                print(f"[Debug] Temperature: {self.temperature}")
                print(f"[Debug] Tools count: {len(tool_defs) if tool_defs else 0}")
                
                # Log last 3 messages for inspection
                for idx, msg in enumerate(sanitized_messages[-3:]):
                    role = msg.get('role', 'unknown')
                    content_preview = str(msg.get('content', ''))[:200] if msg.get('content') else '[NO CONTENT]'
                    has_tool_calls = 'tool_calls' in msg and msg['tool_calls'] is not None
                    has_tool_call_id = 'tool_call_id' in msg and msg['tool_call_id'] is not None
                    print(f"[Debug] Msg {idx} | Role: {role} | Content: {content_preview}")
                    if has_tool_calls:
                        print(f"[Debug]        | Has tool_calls: {len(msg['tool_calls'])}")
                    if has_tool_call_id:
                        print(f"[Debug]        | Tool call ID: {msg['tool_call_id']}")
                print(f"[Debug] ===== END DEBUG =====\n")

                try:
                    # v6.1: Added Timeout (120s) to prevent infinite hangs
                    response = completion_with_retry(
                        model=self.model_name,
                        messages=sanitized_messages,
                        tools=tool_defs,
                        api_key=api_key,
                        temperature=self.temperature,
                        max_tokens=self.config.model_config.max_tokens,
                        top_p=self.config.model_config.top_p,
                        custom_llm_provider=custom_provider,
                        timeout=120 # Safety Net
                    )
                except litellm.exceptions.RateLimitError as e:
                    error_msg = f"Rate Limit Hit (429) for model {self.model_name}. Retries exhausted. Please wait ~1 min."
                    print(f"[{self.model_name}] {error_msg}")
                    return {"success": False, "error": error_msg}
                except Exception as e:
                    error_msg = f"LLM Call Failed: {type(e).__name__}: {str(e)}"
                    print(f"[Loop] ❌ {error_msg}")
                    import traceback
                    traceback.print_exc()
                    return {"success": False, "error": error_msg}
                
                # Debug: Log response structure
                print(f"[Debug] Response type: {type(response)}")
                print(f"[Debug] Has choices: {hasattr(response, 'choices')}")
                if hasattr(response, 'choices'):
                    print(f"[Debug] Choices length: {len(response.choices) if response.choices else 0}")
                    if response.choices and len(response.choices) > 0:
                        print(f"[Debug] First choice: {response.choices[0]}")
                        print(f"[Debug] Message: {response.choices[0].message if hasattr(response.choices[0], 'message') else 'NO MESSAGE'}")
                
                if not response.choices or not response.choices[0].message:
                    error_detail = "Response structure invalid"
                    if not response.choices:
                        error_detail = "response.choices is None or empty"
                    elif not response.choices[0].message:
                        error_detail = "response.choices[0].message is None"
                    print(f"[Loop] ❌ Empty response from LLM: {error_detail}")
                    return {"success": False, "error": f"Empty response from LLM: {error_detail}"}
                
                response_message = response.choices[0].message
                messages.append(response_message)
                
                # [Fix] Update Valid Content Tracker IMMEDIATELY
                # Capture content even if we subsequently 'continue' due to tool calls
                if response_message.content:
                    last_valid_content = response_message.content

                # DB Assistant Msg
                if self.conversation_id:
                    tool_calls_data = None
                    if response_message.tool_calls:
                         tool_calls_data = [{"id": tc.id, "type": tc.type, "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in response_message.tool_calls]
                    
                    db.add_message(DBMessage(
                        conversation_id=self.conversation_id,
                        role="assistant",
                        content=response_message.content or "",
                        tool_calls=tool_calls_data
                    ))

                print(f"[LLM Message] {response_message.content}")
                
                # [Guard Rail] Catch empty responses causing infinite loops
                # Check for thinking blocks (Gemini 2.0 Thinking support)
                has_thoughts = False
                try:
                    if hasattr(response_message, 'thinking_blocks') and response_message.thinking_blocks:
                        has_thoughts = True
                    # Fallback check for provider fields if litellm puts it there
                    elif hasattr(response_message, 'provider_specific_fields') and response_message.provider_specific_fields:
                        if 'thinking_blocks' in response_message.provider_specific_fields:
                             has_thoughts = True
                except: pass

                if not response_message.content and not response_message.tool_calls:
                     # Check Finish Reason
                     finish_reason = None
                     try:
                        if hasattr(response, 'choices') and response.choices:
                            finish_reason = getattr(response.choices[0], 'finish_reason', None)
                     except: pass

                     # [Fix] If model thought but didn't speak, NUDGE it instead of stopping
                     if has_thoughts and finish_reason == "stop":
                         print(f"[Loop] 🧠 Model produced thoughts ({len(response_message.thinking_blocks) if hasattr(response_message, 'thinking_blocks') else '?'} blocks) but no content. Nudging...")
                         messages.append({
                             "role": "user", 
                             "content": "System: You have completed your thinking process. Now please provide the final response based on your reasoning."
                         })
                         continue

                     if finish_reason == "stop":
                         print(f"[Loop] 🛑 Model signaled STOP with empty content. Ending turn.")
                         # Return the last valid content we saw (from previous iteration), or a status if none.
                         if last_valid_content:
                             print(f"[Loop] Returning previous valid content ({len(last_valid_content)} chars).")
                             return {"success": True, "output": last_valid_content}
                         return {"success": True, "output": "(Model finished)"}

                     print(f"[Loop] ⚠️ Empty Response detected (Reason: {finish_reason}). Attempting rescue...")
                     # Rescue Strategy: Nudge the model to continue
                     messages.append({
                         "role": "user", 
                         "content": "System: The previous response was empty. Please generate the final response based on the available context."
                     })
                     continue # Jump to next iteration to retry generation
                
                # v5.5: Check for Delegation Protocol
                import re
                delegation_match = re.search(r'\[CALLING AGENT:\s*(.*?)\]', response_message.content or "", re.IGNORECASE)
                if delegation_match:
                    target_agent_name = delegation_match.group(1).strip()
                    # Determine context for sub-agent (usually the last user query + this response's rationale)
                    delegation_context = f"User Request: {user_query}\nRationale: {response_message.content}"
                    
                    delegation_result = self._handle_agent_delegation(target_agent_name, delegation_context)
                    
                    # Inject result as SYSTEM message
                    messages.append({
                        "role": "system", 
                        "content": delegation_result
                    })
                    print(f"[Loop] Delegation complete. Continuing loop with sub-agent context...")
                    continue # Continue loop to let Main Agent synthesize the result

                # Process Tool Calls
                if response_message.tool_calls:
                    print("[Agent] Calling tools...")
                    # [Anti-Loop] Track executed tools to prevent infinite re-query loops
                    if not hasattr(self, '_seen_tool_signatures') or i == 0:
                         self._seen_tool_signatures = set()
                    
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        # Anti-Loop Check (Ignore duplicate tool calls with same args in the same turn)
                        tool_signature = f"{function_name}_{json.dumps(function_args, sort_keys=True)}"
                        if tool_signature in self._seen_tool_signatures:
                             print(f"[Loop] ⚠️ Caught Infinite Tool Loop attempt for '{function_name}'. Forcing stop.")
                             messages.append({
                                 "tool_call_id": tool_call.id,
                                 "role": "tool",
                                 "name": function_name,
                                 "content": json.dumps({"error": "Anti-Loop Triggered: You have already executed this exact tool search/action in this turn. Rely on the context you have and provide your final textual answer to the user now."}, ensure_ascii=False)
                             })
                             continue
                        
                        self._seen_tool_signatures.add(tool_signature)
                        
                        function_args = self.resolve_path_aliases(function_args)
                        
                        # Writing Plan State
                        if "writing_plan" in function_args:
                            self.current_writing_plan = function_args["writing_plan"]

                        # Execute Tool
                        if function_name in available_tools_map:
                            function_to_call = available_tools_map[function_name]
                            
                            # Inject specific context
                            if function_name == "rag_query":
                                function_args["corpus_id"] = self.corpus_id
                                function_args["agent_persona"] = self.system_instruction # Enable Matrix Pivot
                                rag_called_in_loop = True
                            elif function_name == "update_memory":
                                function_args["conversation_id"] = self.conversation_id
                            
                            try:
                                tool_output = function_to_call(**function_args)
                            except Exception as e:
                                tool_output = f"Error: {e}"
                            
                            # Add Tool Output
                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": json.dumps({"result": tool_output}, ensure_ascii=False)
                            })
                            
                            # DB Tool Msg
                            if self.conversation_id:
                                db.add_message(DBMessage(
                                    conversation_id=self.conversation_id,
                                    role="tool",
                                    content=json.dumps({"result": tool_output}, ensure_ascii=False),
                                    tool_call_id=tool_call.id,
                                    name=function_name
                                ))
                        else:
                            messages.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool", 
                                "name": function_name,
                                "content": json.dumps({"error": "Tool not found"}, ensure_ascii=False)
                            })
                    
                    # Next Step Instruction
                    instruction = "Tool execution complete. Proceed logically."
                    if self.current_writing_plan:
                         instruction += f"\n[STATE] Plan: {self.current_writing_plan}"
                    messages.append({"role": "user", "content": instruction})
                    continue
                
                # Final Response handling
                final_text = response_message.content or ""
                
                # Cost Governor (v6.1)
                if hasattr(response, 'usage'):
                    in_tokens = response.usage.prompt_tokens
                    out_tokens = response.usage.completion_tokens
                    
                    # Pricing (Approximate Blended Rate based on Gemini 1.5 Flash)
                    # Input: $0.075 / 1M tokens
                    # Output: $0.30 / 1M tokens
                    # We use a slightly higher safety buffer
                    cost_in = in_tokens * (0.0000001) 
                    cost_out = out_tokens * (0.0000004)
                    turn_cost = cost_in + cost_out
                    self.session_cost += turn_cost
                    
                    print(f"[💰 Cost Governor] Turn: ${turn_cost:.5f} | Total: ${self.session_cost:.4f}")
                    
                    if self.session_cost > 2.00:
                        raise Exception(f"SAFETY SHUTDOWN: Session cost exceeded limit (${self.session_cost:.2f} > $2.00).")

                # Active Scanner (v6.0 - Persona-Aware)
                if final_text:
                    print("[Active Scanner] Analyzing turn for critical facts...")
                    # Pass system_instruction as persona context
                    self._scan_and_save_facts(user_query, final_text, agent_context=self.system_instruction)

                # [CRITICAL FIX] Exit loop if no tools were called
                # If we have content and no tools, the turn is over.
                if not response_message.tool_calls:
                    print(f"[Loop] ✅ Final answer received. Exiting loop.")
                    
                    token_usage = {}
                    if hasattr(response, 'usage'):
                        token_usage = {'total': response.usage.total_tokens}

                    return {
                        "output": final_text,
                        "success": True, 
                        "token_usage": token_usage,
                        "rag_score": getattr(self, 'last_rag_score', 0),
                        "cost": self.session_cost
                    }

                # Fallback: If for some reason we are here with tools (should be impossible due to continue), return text.
                return {"success": True, "output": final_text}

            except Exception as e:
                import traceback
                print(f"Loop Error: {e}")
                print(traceback.format_exc())
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Max iterations reached"}

    def run_loop(self, user_query: str, history: list[dict] | None = None, stream_callback=None, approved_operations: dict | None = None, max_turns: int = 10):
        print("\n========== AGENT START ==========")
        
        # 1. Inject File Context (BEFORE RAG CHECK)
        user_query = self._inject_file_context(user_query)
        print(f"[User Query] {user_query[:500]}..." if len(user_query) > 500 else f"[User Query] {user_query}")

        print(f"[Config] Temperature={self.config.model_config.temperature}")
        
        # 2. History & Setup
        db_history = []
        if self.conversation_id:
            print(f"[DB] Fetching history for conversation {self.conversation_id}")
            # Limit history to last 20 messages (User Request)
            db_messages = db.get_history(self.conversation_id, limit=35)
            
            for msg in db_messages:
                # FILTER: Do not load old System messages or RAG injections
                if msg.role == "system" or "[KNOWLEDGE BASE CONTEXT" in (msg.content or ""):
                    continue
                    
                message_dict = {"role": msg.role, "content": msg.content}
                if msg.tool_calls: message_dict["tool_calls"] = msg.tool_calls
                if msg.tool_call_id: message_dict["tool_call_id"] = msg.tool_call_id
                if msg.name: message_dict["name"] = msg.name
                db_history.append(message_dict)
            print(f"[DB] Loaded {len(db_history)} messages from history (Filtered)")
            
            # Save user query
            from .models import Message as DBMessage
            db.add_message(DBMessage(conversation_id=self.conversation_id, role="user", content=user_query))
            db.update_conversation_timestamp(self.conversation_id)
        elif history:
            db_history = history
            print(f"[History] Using transient history: {len(history)} messages")

        # 3. Build Messages
        messages = [{"role": "system", "content": self.system_instruction}]
        
        # 4. Inject Memory Context (Merge into System Prompt)
        # This is the CORRECT architecture - memory as implicit knowledge, not user messages
        memory_injections = self._inject_memory_context(db_history, user_query)
        if memory_injections:
            for injection in memory_injections:
                if injection.get("role") == "system":
                    # Merge system-level injections into the system prompt
                    messages[0]["content"] += "\n\n" + injection["content"]
                    print(f"[Loop] Merged memory context into System Prompt.")
        
        # 5. Append History (Normal flow)
        messages.extend([msg for msg in db_history if msg.get("role") != "system"])
            
        # 6. Append Current User Query
        messages.append({"role": "user", "content": user_query})
        
        # 6. Pre-Emptive RAG
        rag_injections = self._execute_pre_emptive_rag(user_query, db_history)
        if rag_injections:
            print(f"[Loop] Merging {len(rag_injections)} RAG blocks into System Prompt.")
            for inj in rag_injections:
                # Merge into System Prompt (messages[0]) to avoid "User Input" confusion
                messages[0]["content"] += "\n\n" + inj["content"] 
            
        # 7. Execute Turn
        return self._execute_agent_turn(messages, user_query, stream_callback, approved_operations, max_turns=max_turns)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interact with the Communication Expert Agent.")
    parser.add_argument("--query", type=str, required=True, help="The query for the agent.")
    args = parser.parse_args()
    
    # Get the default configuration and create an agent instance
    agent_config = get_default_config()
    agent = Agent(config=agent_config)
    
    final_output = agent.run_loop(args.query)
    print(f"\nFinal Agent Output: {final_output}")
