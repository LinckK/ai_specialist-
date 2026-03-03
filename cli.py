import sys
import asyncio
import argparse
from typing import Optional

# Add project root to path to ensure imports work
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from agent_project.agent import Agent
from agent_project.config import get_default_config, AgentConfig, ModelConfig, RAGConfig
from agent_project.agent_registry import get_registry, AgentProfile
from agent_project.db import db
from agent_project.tools.corpus_manager import list_corpus_files
from agent_project.tools.upload_tool import upload_file_to_corpus, validate_file

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_welcome():
    print("\n" + Colors.HEADER + "="*50 + Colors.ENDC)
    print(Colors.BOLD + Colors.CYAN + "🤖  Agent System CLI  🤖" + Colors.ENDC)
    print(Colors.HEADER + "="*50 + Colors.ENDC)

def list_available_agents():
    registry = get_registry()
    agents = registry.list_agents()
    print("\nAvailable Agents:")
    for i, agent in enumerate(agents):
        print(f" [{i+1}] {agent.name}: {agent.description}")
    return agents

def get_multiline_input(prompt: str) -> str:
    """
    Reads multi-line input from user.
    Supports loading from file or pasting.
    """
    print(f"{prompt}")
    print("Select input method:")
    print(" [1] Load from text file")
    print(" [2] Type or Paste text (Multi-line)")
    
    choice = input(">> ").strip()
    
    # Option 1: Load from File
    if choice == '1' or choice.upper().startswith("FILE:"):
        file_path = ""
        if choice == '1':
            file_path = input("Enter full file path: ").strip()
        else:
            file_path = choice[5:].strip()
            
        # Remove quotes if present
        if (file_path.startswith('"') and file_path.endswith('"')) or \
           (file_path.startswith("'") and file_path.endswith("'")):
            file_path = file_path[1:-1]
            
        try:
            from pathlib import Path
            # Check if file exists
            path_obj = Path(file_path)
            if not path_obj.exists():
                print(f"❌ File not found: {file_path}")
                return get_multiline_input(prompt)
                
            content = path_obj.read_text(encoding='utf-8')
            print(f"✅ Loaded {len(content)} characters from {path_obj.name}")
            return content
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return get_multiline_input(prompt)

    # Option 2: Paste/Type
    print("(Paste your text now. Press Ctrl+Z then Enter on a new line to finish)")
    lines = []
    # If user typed something else (like the start of text), keep it
    if choice != '2' and choice:
        lines.append(choice)
        
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines)

def create_new_agent_interactive():
    print("\n--- Create New Agent ---")
    name = input("Agent Name (e.g., 'coder'): ").strip()
    if not name:
        print("Name is required.")
        return

    description = input("Description: ").strip()
    
    print("\nSystem Prompt (What is the agent's role?):")
    system_prompt = get_multiline_input(">>")
    
    # Default Configs
    model_config = ModelConfig(litellm_model_name="gemini/gemini-2.0-flash-lite")
    rag_config = RAGConfig(corpus_id=None) # Set to None to trigger AUTO-CREATION in registry
    
    config = AgentConfig(
        model_config=model_config,
        rag_config=rag_config,
        base_system_prompt=system_prompt
    )
    
    profile = AgentProfile(
        name=name,
        description=description,
        config=config
    )
    
    registry = get_registry()
    if registry.register_agent(profile):
        print(f"\n✅ Agent '{name}' created successfully!")
    else:
        print(f"\n❌ Failed to create agent '{name}'.")

def manage_agents_menu():
    """Submenu for managing agents"""
    while True:
        print("\n--- Manage Agents ---")
        print(" [1] List All Agents")
        print(" [2] Create New Agent")
        print(" [3] Configure Agent")
        print(" [4] Delete Agent")
        print(" [5] Back to Main Menu")
        
        choice = input("\nSelect an option: ").strip()
        
        if choice == '1':
            list_available_agents()
        
        elif choice == '2':
            create_new_agent_interactive()
        
        elif choice == '3':
            configure_agent_interactive()
        
        elif choice == '4':
            delete_agent_interactive()
        
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")

def configure_agent_interactive():
    """Interactive agent configuration"""
    try:
        print("\n--- Configure Agent ---")
        agents = list_available_agents()
        if not agents:
            print("No agents available.")
            return
        
        agent_name = input("\nEnter agent name to configure: ").strip()
        if not agent_name:
            return
        
        registry = get_registry()
        agent_profile = registry.get_agent(agent_name)
        
        if not agent_profile:
            print(f"Agent '{agent_name}' not found.")
            return
        
        while True:
            print(f"\n--- Agent Configuration: {agent_name} ---")
            print(f"  Model: {agent_profile.config.model_config.litellm_model_name}")
            print(f"  Temperature: {agent_profile.config.model_config.temperature}")
            print(f"  Max Tokens: {agent_profile.config.model_config.max_tokens}")
            
            # Safe access to corpus_id
            corpus_id = "None"
            if hasattr(agent_profile.config, 'rag_config') and agent_profile.config.rag_config:
                corpus_id = agent_profile.config.rag_config.corpus_id or "None"
            print(f"  Corpus ID: {corpus_id}")
            
            print("\n [1] Change Model")
            print(" [2] Change Temperature")
            print(" [3] Change Max Tokens")
            print(" [4] Edit System Prompt")
            print(" [5] Upload Files to Knowledge Base")
            print(" [6] View Corpus Files")
            print(" [7] Back")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                print("\nAvailable Models:")
                models = [
                    "gemini/gemini-3-flash-001",
                    "gemini/gemini-3-pro-preview"
                ]
                for i, model in enumerate(models, 1):
                    print(f" [{i}] {model}")
                
                model_choice = input("Select model (or enter custom): ").strip()
                if model_choice.isdigit() and 1 <= int(model_choice) <= len(models):
                    agent_profile.config.model_config.litellm_model_name = models[int(model_choice)-1]
                    registry.update_agent(agent_name, agent_profile.config)
                    print("✅ Model updated!")
                elif model_choice:
                    agent_profile.config.model_config.litellm_model_name = model_choice
                    registry.update_agent(agent_name, agent_profile.config)
                    print("✅ Model updated!")
            
            elif choice == '2':
                temp = input(f"Enter temperature (0.0-2.0, current: {agent_profile.config.model_config.temperature}): ").strip()
                try:
                    temp = float(temp)
                    if 0.0 <= temp <= 2.0:
                        agent_profile.config.model_config.temperature = temp
                        registry.update_agent(agent_name, agent_profile.config)
                        print("✅ Temperature updated!")
                    else:
                        print("❌ Temperature must be between 0.0 and 2.0")
                except ValueError:
                    print("❌ Invalid temperature")
            
            elif choice == '3':
                tokens = input(f"Enter max tokens (current: {agent_profile.config.model_config.max_tokens}): ").strip()
                try:
                    tokens = int(tokens)
                    if tokens > 0:
                        agent_profile.config.model_config.max_tokens = tokens
                        registry.update_agent(agent_name, agent_profile.config)
                        print("✅ Max tokens updated!")
                    else:
                        print("❌ Max tokens must be positive")
                except ValueError:
                    print("❌ Invalid number")
            
            elif choice == '4':
                print(f"\nCurrent System Prompt:\n{agent_profile.config.base_system_prompt}\n")
                print("Enter new system prompt (or press Enter to cancel):")
                new_prompt = get_multiline_input(">>")
                if new_prompt:
                    agent_profile.config.base_system_prompt = new_prompt
                    registry.update_agent(agent_name, agent_profile.config)
                    print("✅ System prompt updated!")
            
            elif choice == '5':
                upload_files_to_agent(agent_name, agent_profile)
            
            elif choice == '6':
                view_corpus_files(agent_profile)
            
            elif choice == '7':
                break
            else:
                print("Invalid choice.")
    except Exception as e:
        print(f"\n❌ Error in configuration menu: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to return to menu...")

def upload_files_to_agent(agent_name: str, agent_profile: AgentProfile):
    """Upload files to an agent's knowledge base.
    Supports both a list of file paths and a single folder path (recursively uploads all supported files)."""
    print(f"\n--- Upload Files to {agent_name} ---")

    # Check if agent has a corpus
    if not hasattr(agent_profile.config, 'rag_config') or not agent_profile.config.rag_config or not agent_profile.config.rag_config.corpus_id:
        print("❌ This agent doesn't have a knowledge base corpus.")
        print("   Cannot upload files without a corpus.")
        return

    corpus_id = agent_profile.config.rag_config.corpus_id
    print(f"\nCorpus ID: {corpus_id}")
    print("Supported formats: PDF, TXT, MD, DOCX (max 32MB each)")

    # Prompt for paths (one per line). Users can paste a list or a single folder path.
    print("\nEnter file or folder paths to upload (one per line).")
    print("You can paste a list of paths or just a single folder.")
    paths_text = get_multiline_input("Paths:")
    if not paths_text.strip():
        print("No files specified.")
        return

    raw_paths = [p.strip() for p in paths_text.split('\n') if p.strip()]
    file_paths = []
    import os
    for raw_path in raw_paths:
        # Clean up possible "File path:" prefix
        if raw_path.lower().startswith("file path:"):
            raw_path = raw_path[10:].strip()
        # Remove surrounding quotes
        if (raw_path.startswith('"') and raw_path.endswith('"')) or (raw_path.startswith("'") and raw_path.endswith("'")):
            raw_path = raw_path[1:-1]
            
        # If it's a directory, walk recursively and collect supported files
        if os.path.isdir(raw_path):
            print(f"📂 Found folder: {raw_path} - scanning for files...")
            for root_dir, _, files in os.walk(raw_path):
                for f in files:
                    # Filter for supported extensions if needed, or just let upload tool handle it
                    if f.lower().endswith(('.pdf', '.txt', '.md', '.docx')):
                        file_paths.append(os.path.join(root_dir, f))
        else:
            file_paths.append(raw_path)

    print(f"\n📤 Uploading {len(file_paths)} file(s)...")
    successful = 0
    failed = 0

    for file_path in file_paths:
        # Validate file first
        is_valid, error = validate_file(file_path)
        if not is_valid:
            print(f"❌ {file_path}: {error}")
            failed += 1
            continue
        # Upload
        result = upload_file_to_corpus(file_path, corpus_id)
        if result["success"]:
            print(f"✅ {result['display_name']} - {result['size_bytes'] / 1024:.1f} KB")
            successful += 1
        else:
            print(f"❌ {file_path}: {result['message']}")
            failed += 1

    print(f"\n📊 Upload Summary: {successful} successful, {failed} failed")
    input("\nPress Enter to continue...")

def view_corpus_files(agent_profile: AgentProfile):
    """View files in an agent's corpus"""
    print("\n--- Knowledge Base Files ---")
    
    if not hasattr(agent_profile.config, 'rag_config') or not agent_profile.config.rag_config or not agent_profile.config.rag_config.corpus_id:
        print("❌ This agent doesn't have a knowledge base corpus.")
        return
    
    corpus_id = agent_profile.config.rag_config.corpus_id
    print(f"Corpus ID: {corpus_id}\n")
    
    try:
        files = list_corpus_files(corpus_id)
        
        if not files:
            print("📭 No files in knowledge base.")
        else:
            print(f"📚 {len(files)} file(s) in knowledge base:\n")
            for i, file in enumerate(files, 1):
                display_name = file.get('display_name', 'Unknown')
                size = file.get('size_bytes', 'Unknown')
                if isinstance(size, int):
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = str(size)
                print(f" [{i}] {display_name} - {size_str}")
    
    except Exception as e:
        print(f"❌ Error listing files: {e}")
    
    input("\nPress Enter to continue...")

def delete_agent_interactive():
    """Delete an agent"""
    print("\n--- Delete Agent ---")
    agents = list_available_agents()
    if not agents:
        print("No agents available.")
        return
    
    agent_name = input("\nEnter agent name to delete: ").strip()
    if not agent_name:
        return
    
    if agent_name == "default":
        print("❌ Cannot delete the default agent.")
        return
    
    confirm = input(f"⚠️  Are you sure you want to delete '{agent_name}'? (yes/no): ").strip().lower()
    if confirm == "yes":
        registry = get_registry()
        if registry.delete_agent(agent_name):
            print(f"✅ Agent '{agent_name}' deleted.")
        else:
            print(f"❌ Failed to delete agent '{agent_name}'.")
    else:
        print("Deletion cancelled.")

def view_conversation_history():
    """View past conversations"""
    print("\n--- Conversation History ---")
    
    try:
        # Get recent conversations
        convs = db.client.table("conversations").select("*").order("updated_at", desc=True).limit(20).execute()
        
        if not convs.data:
            print("No conversations found.")
            return
        
        print("\nRecent Conversations:")
        for i, conv in enumerate(convs.data, 1):
            title = conv.get('title', 'Untitled')
            created = conv.get('created_at', '')[:10]  # Just the date
            print(f" [{i}] {title} - {created}")
        
        choice = input("\nSelect conversation to view (or 'b' to go back): ").strip()
        
        if choice == 'b':
            return
        
        if choice.isdigit() and 1 <= int(choice) <= len(convs.data):
            conv = convs.data[int(choice)-1]
            display_conversation_detail(conv['id'])
        else:
            print("Invalid choice.")
            
    except Exception as e:
        print(f"\n❌ Error fetching history: {e}")
        print("Check your internet connection and Supabase configuration.")
        input("\nPress Enter to return...")

def display_conversation_detail(conversation_id: str):
    """Display conversation messages"""
    messages = db.get_history(conversation_id)
    
    print(f"\n{'='*60}")
    print(f"Conversation: {conversation_id}")
    print(f"{'='*60}\n")
    
    for msg in messages:
        role_icon = "👤" if msg.role == "user" else "🤖" if msg.role == "assistant" else "🔧"
        content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
        print(f"{role_icon} {msg.role.upper()}: {content}\n")
    
    print(f"{'='*60}")
    
    # Offer to resume or delete the conversation
    print("\nOptions:")
    print("1. Resume this conversation")
    print("2. Delete this conversation")
    print("3. Back to list")
    
    choice = input("\nChoose an option (1/2/3): ").strip()
    
    if choice == '1':
        # Resume conversation
        # Get the conversation to determine which agent was used
        conv_data = db.client.table("conversations").select("*").eq("id", conversation_id).execute()
        if conv_data.data:
            # Extract agent name from title or use default
            title = conv_data.data[0].get('title', '')
            agent_name = "default"  # Default fallback
            if "- " in title:
                agent_name = title.split("- ")[-1]
            
            print(f"\nResuming conversation with agent: {agent_name}")
            run_agent_session(agent_name, new_conversation=False, existing_conversation_id=conversation_id)
    
    elif choice == '2':
        # Delete conversation
        confirm = input("\n⚠️  Are you sure you want to delete this conversation? This cannot be undone. (yes/no): ").strip().lower()
        if confirm == 'yes':
            if db.delete_conversation(conversation_id):
                print("✅ Conversation deleted successfully.")
                input("\nPress Enter to continue...")
            else:
                print("❌ Failed to delete conversation.")
                input("\nPress Enter to continue...")
        else:
            print("Deletion cancelled.")
            input("\nPress Enter to continue...")
    
    elif choice == '3':
        # Back to list - do nothing, just return
        pass
    else:
        print("Invalid option.")

DEBUG_MODE = False  # Global flag for debug mode

def run_agent_session(agent_name: str, new_conversation: bool = False, existing_conversation_id: Optional[str] = None):
    registry = get_registry()
    agent_profile = registry.get_agent(agent_name)
    
    if not agent_profile:
        print(f"Error: Agent '{agent_name}' not found.")
        return

    print(f"\nStarting session with agent: {agent_name}")
    if DEBUG_MODE:
        print(f"{Colors.WARNING}🔧 DEBUG MODE ENABLED{Colors.ENDC}")
    
    # Determine conversation ID
    conversation_id = None
    if existing_conversation_id:
        # Resume existing conversation
        conversation_id = existing_conversation_id
        print(f"Resuming conversation: {conversation_id}")
    elif new_conversation:
        # Create new conversation with unique title
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        conv = db.create_conversation(title=f"Chat {timestamp} - {agent_name}")
        conversation_id = str(conv.id)
        print(f"Created new conversation: {conversation_id}")
    else:
        # Default: create new conversation
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        conv = db.create_conversation(title=f"Chat {timestamp} - {agent_name}")
        conversation_id = str(conv.id)
        print(f"Created new conversation: {conversation_id}")

    # Initialize Agent
    agent = Agent(
        config=agent_profile.config,
        conversation_id=conversation_id
    )

    print("\nType 'exit', 'quit', or 'bye' to end the session.")
    print("Type '/agent <name>' to switch agents.")

    first_message = True
    while True:
        try:
            user_input = input(f"\n👤 You ({agent_profile.name}): ").strip()
            
            # --- Multi-line Paste Mode ---
            if user_input == ":paste":
                print("📝 Paste Mode Enabled. Paste your text below.")
                print("Type 'END' on a new line to submit.")
                lines = []
                while True:
                    try:
                        line = input()
                        if line.strip() == "END":
                            break
                        lines.append(line)
                    except EOFError:
                        break
                user_input = "\n".join(lines)
                print(f"✅ Received {len(lines)} lines.")
            # -----------------------------
            
            if not user_input:
                continue
            
            # Update conversation title with first message
            if first_message and not existing_conversation_id:
                preview = user_input[:50] + "..." if len(user_input) > 50 else user_input
                db.client.table("conversations").update({
                    "title": f"{preview} - {agent_name}"
                }).eq("id", conversation_id).execute()
                first_message = False
                
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\n👋 Goodbye!")
                break
            
            if user_input.startswith("/agent "):
                new_agent_name = user_input.split(" ")[1]
                new_profile = registry.get_agent(new_agent_name)
                if new_profile:
                    agent_profile = new_profile
                    # Update agent instance with new config but KEEP conversation history
                    agent = Agent(
                        config=agent_profile.config,
                        conversation_id=conversation_id
                    )
                    print(f"\n🔄 Switched to agent: {new_agent_name}")
                else:
                    print(f"\n❌ Agent '{new_agent_name}' not found.")
                continue

            # Run Agent
            print("\n" + Colors.HEADER + "─"*50 + Colors.ENDC)
            print(Colors.CYAN + "🤖 Thinking..." + Colors.ENDC, end="", flush=True)
            
            # Track timing if debug mode
            import time
            start_time = time.time() if DEBUG_MODE else None
            
            # Track approved operations by tool_call.id (simple!)
            approved_ops = {}
            
            while True:  # Loop to handle approval flow
                result = agent.run_loop(user_input, approved_operations=approved_ops)
                
                # Debug: Show execution time
                if DEBUG_MODE and start_time:
                    elapsed = time.time() - start_time
                    print(f"\n{Colors.WARNING}⏱️  Execution Time: {elapsed:.2f}s{Colors.ENDC}")
                
                print("\r" + " "*20 + "\r", end="")

                if result.get("status") == "WAITING_APPROVAL":
                    tool_name = result.get("tool_name")
                    tool_args = result.get("tool_args", {})
                    op_signature = result.get("operation_signature")  # Use signature instead of tool_call_id
                    
                    # Show what agent wants to do
                    print(f"\n{Colors.WARNING}⚠️  PERMISSION REQUEST: {tool_name}{Colors.ENDC}")
                    print(f"   {Colors.WARNING}{'─'*30}{Colors.ENDC}")
                    if tool_name == "execute_cmd":
                        print(f"   Command:   {Colors.BOLD}{tool_args.get('command')}{Colors.ENDC}")
                        if tool_args.get('working_dir'):
                            print(f"   Directory: {tool_args.get('working_dir')}")
                    elif tool_name == "create_directory":
                        print(f"   Directory: {Colors.BOLD}{tool_args.get('directory_path')}{Colors.ENDC}")
                    elif tool_name == "write_file":
                        print(f"   File:      {Colors.BOLD}{tool_args.get('file_path')}{Colors.ENDC}")
                        content_preview = tool_args.get('content', '')[:100] + "..." if len(tool_args.get('content', '')) > 100 else tool_args.get('content', '')
                        print(f"   Content:   {content_preview}")
                    elif tool_name ==  "delete_file":
                        print(f"   File:      {Colors.FAIL}{tool_args.get('file_path')}{Colors.ENDC}")
                    print(f"   {Colors.WARNING}{'─'*30}{Colors.ENDC}")
                    
                    approval = input(f"{Colors.BOLD}>> Approve? (y/n): {Colors.ENDC}").strip().lower()
                    if approval == 'y':
                        # Mark this operation as approved by signature
                        approved_ops[op_signature] = True
                        print(f"{Colors.GREEN}✅ Approved. Continuing...{Colors.ENDC}", end="", flush=True)
                        continue  # Re-run agent.run_loop with approval
                    else:
                        print(f"\n{Colors.FAIL}❌ Operation denied.{Colors.ENDC}")
                        break  # Exit approval loop
                
                elif result.get("success"):
                    # Debug: Show internal state and token usage
                    if DEBUG_MODE:
                        print(f"\n{Colors.WARNING}📊 DEBUG INFO:{Colors.ENDC}")
                        if hasattr(agent, 'current_writing_plan'):
                            print(f"   Writing Plan: {agent.current_writing_plan or 'None'}")
                        if hasattr(agent.config, 'rag_config') and agent.config.rag_config:
                            print(f"   RAG Corpus: {agent.config.rag_config.corpus_id}")
                        # Token usage (if available in result)
                        if result.get('token_usage'):
                            usage = result['token_usage']
                            print(f"   Tokens - Thinking: {usage.get('thinking', 0)} | Completion: {usage.get('completion', 0)} | Total: {usage.get('total', 0)}")
                        print(f"{Colors.HEADER}{'─'*50}{Colors.ENDC}")
                    
                    # Display RAG Score (always visible, not just debug)
                    if result.get('rag_score') is not None:
                        score = result['rag_score']
                        if score >= 80:
                            tier = f"{Colors.FAIL}🔴 MANDATORY{Colors.ENDC}"
                        elif score >= 60:
                            tier = f"{Colors.WARNING}🟡 SUGGESTED{Colors.ENDC}"
                        elif score >= 30:
                            tier = f"{Colors.GREEN}🟢 AVAILABLE{Colors.ENDC}"
                        else:
                            tier = f"⚪ HIDDEN"
                        
                        print(f"\n{Colors.BOLD}🧠 RAG Decision:{Colors.ENDC} Score {score}/100 → {tier}")
                    
                    print(f"\n{Colors.BLUE}🤖 {agent_profile.name}:{Colors.ENDC}")
                    print(f"{Colors.HEADER}{'─'*50}{Colors.ENDC}")
                    
                    output = result.get('output', '')
                    
                    # Parse and display <thinking> block
                    import re
                    thinking_match = re.search(r'<thinking>(.*?)</thinking>', output, re.DOTALL)
                    
                    if thinking_match:
                        thinking_content = thinking_match.group(1).strip()
                        # Remove the thinking block from the main output
                        final_output = output.replace(thinking_match.group(0), "").strip()
                        
                        print(f"{Colors.WARNING}🧠 Raciocínio (Chain of Thought):{Colors.ENDC}")
                        # Print thinking content indented/dimmed
                        for line in thinking_content.split('\n'):
                            print(f"   {Colors.WARNING}│ {line}{Colors.ENDC}")
                        print(f"{Colors.HEADER}{'─'*50}{Colors.ENDC}")
                        print(f"{final_output}")
                    else:
                        print(f"{output}")
                        
                    print(f"{Colors.HEADER}{'─'*50}{Colors.ENDC}")
                    break  # Success, exit approval loop
                else:
                    print(f"\n{Colors.FAIL}❌ Error: {result.get('error')}{Colors.ENDC}")
                    break  # Error, exit approval loop

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Unexpected Error: {e}")

def interactive_menu():
    print_welcome()
    while True:
        print("\nMain Menu:")
        print(" [1] Chat with Agent")
        print(" [2] Manage Agents")
        print(" [3] View Conversation History")
        print(" [4] Exit")
        
        choice = input("\nSelect an option: ").strip()
        
        if choice == '1':
            agents = list_available_agents()
            if not agents:
                print("No agents available.")
                continue
            
            name = input("\nEnter Agent Name to start (or press Enter for 'default'): ").strip()
            if not name:
                name = "default"
            run_agent_session(name, new_conversation=True)
        
        elif choice == '2':
            manage_agents_menu()
        
        elif choice == '3':
            view_conversation_history()
        
        elif choice == '4':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

def main():
    parser = argparse.ArgumentParser(description="Run the AI Agent in CLI mode.")
    parser.add_argument("--agent", type=str, help="Name of the agent to start with.")
    parser.add_argument("--new", action="store_true", help="Start a new conversation.")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging.")
    args = parser.parse_args()
    
    # Store debug flag globally for access in run_agent_session
    global DEBUG_MODE
    DEBUG_MODE = args.debug

    # If arguments are provided, bypass the menu
    if args.agent:
        run_agent_session(args.agent, new_conversation=args.new)
    else:
        interactive_menu()

if __name__ == "__main__":
    main()
