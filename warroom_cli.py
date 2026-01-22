"""
War Room CLI - Interactive Conversational Interface

Based on agent CLI but adapted for War Room Protocol v2.0.
Supports: conversation persistence, free mode, strategic analysis mode.

EXECUTION:
    cd C:\Users\gabri\MyWorkspace
    python -m agent_project.warroom_cli
    
Or with arguments:
    python -m agent_project.warroom_cli --mode GROWTH
    python -m agent_project.warroom_cli --free  (for non-business chat)
"""

import sys
import asyncio
import argparse
from typing import Optional
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from agent_project.war_room_kernel import WarRoomKernel
from agent_project.db import db
from agent_project.agent import Agent
from agent_project.config import get_default_config


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_welcome(mode: str = "strategic"):
    """Display welcome banner."""
    print("\n" + Colors.HEADER + "="*60 + Colors.ENDC)
    if mode == "strategic":
        print(Colors.BOLD + Colors.CYAN + "🎯  WAR ROOM - Neural Boardroom  🎯" + Colors.ENDC)
        print(Colors.WARNING + "Strategic Analysis Mode" + Colors.ENDC)
    else:
        print(Colors.BOLD + Colors.GREEN + "💬  WAR ROOM - Free Discussion Mode  💬" + Colors.ENDC)
        print(Colors.CYAN + "Casual Conversation" + Colors.ENDC)
    print(Colors.HEADER + "="*60 + Colors.ENDC)


def select_decision_mode() -> str:
    """Let user select SPEED/GROWTH/SCALE mode."""
    print("\n" + Colors.BOLD + "Select Decision Mode:" + Colors.ENDC)
    print(f"  {Colors.GREEN}[1] SPEED{Colors.ENDC} - Ship Fast (Tech Lead dictates)")
    print(f"  {Colors.WARNING}[2] GROWTH{Colors.ENDC} - Market Domination (CMO dictates)")
    print(f"  {Colors.CYAN}[3] SCALE{Colors.ENDC} - Enterprise Stability (Ethics + Tech alliance)")
    
    choice = input(f"\n{Colors.BOLD}Select mode (1/2/3):{Colors.ENDC} ").strip()
    
    mode_map = {"1": "SPEED", "2": "GROWTH", "3": "SCALE"}
    return mode_map.get(choice, "SPEED")


async def run_strategic_session(conversation_id: Optional[str] = None):
    """
    Run War Room strategic analysis session.
    Continuous conversation mode with memory.
    """
    print_welcome("strategic")
    
    # Determine conversation
    if conversation_id:
        print(f"{Colors.GREEN}Resuming conversation: {conversation_id}{Colors.ENDC}")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        conv = db.create_conversation(title=f"War Room Strategy - {timestamp}")
        conversation_id = str(conv.id)
        print(f"{Colors.GREEN}Created new strategic session: {conversation_id}{Colors.ENDC}")
    
    # Select mode
    decision_mode = select_decision_mode()
    print(f"\n{Colors.BOLD}Active Mode: {decision_mode}{Colors.ENDC}")
    
    # Initialize War Room
    kernel = WarRoomKernel()
    
    print(f"\n{Colors.CYAN}Type 'exit' to end session{Colors.ENDC}")
    print(f"{Colors.CYAN}Type '/mode' to change decision mode{Colors.ENDC}")
    print(f"{Colors.CYAN}Type '/report' to generate full report{Colors.ENDC}")
    
    # Track if this is first message
    first_message = True
    
    while True:
        try:
            user_input = input(f"\n{Colors.BOLD}👤 Strategic Question:{Colors.ENDC} ").strip()
            
            if not user_input:
                continue
            
            # Update conversation title with first message
            if first_message:
                preview = user_input[:50] + "..." if len(user_input) > 50 else user_input
                db.client.table("conversations").update({
                    "title": f"{preview} - War Room"
                }).eq("id", conversation_id).execute()
                first_message = False
            
            # Handle commands
            if user_input.lower() in ["exit", "quit", "bye"]:
                print(f"\n{Colors.GREEN}👋 Strategy session ended.{Colors.ENDC}")
                break
            
            if user_input.lower() == "/mode":
                decision_mode = select_decision_mode()
                print(f"\n{Colors.BOLD}Mode changed to: {decision_mode}{Colors.ENDC}")
                continue
            
            if user_input.lower() == "/report":
                print(f"\n{Colors.CYAN}Generating full report...{Colors.ENDC}")
                # TODO: Save last result to file
                print(f"{Colors.WARNING}Feature coming soon{Colors.ENDC}")
                continue
            
            # Save user message
            db.save_message(
                conversation_id=conversation_id,
                role="user",
                content=user_input
            )
            
            # Execute War Room
            print(f"\n{Colors.HEADER}{'─'*60}{Colors.ENDC}")
            print(f"{Colors.CYAN}🧠 War Room analyzing...{Colors.ENDC}")
            
            result = await kernel.execute(
                user_input=user_input,
                mode=decision_mode,
                client_name="interactive_session"
            )
            
            # Display results
            print(f"\n{Colors.HEADER}{'─'*60}{Colors.ENDC}")
            print(f"{Colors.BOLD}📊 STRATEGIC SYNTHESIS{Colors.ENDC}")
            print(f"{Colors.HEADER}{'─'*60}{Colors.ENDC}")
            
            resolution = result.get('resolution')
            
            if resolution:
                print(f"\n{Colors.BOLD}🏆 Winning Specialist:{Colors.ENDC} {resolution.winning_specialist}")
                print(f"\n{Colors.BOLD}📋 Rationale:{Colors.ENDC}")
                print(f"   {resolution.rationale}")
                
                if resolution.cross_validation_flags:
                    print(f"\n{Colors.WARNING}⚠️  Conflicts Detected:{Colors.ENDC}")
                    for flag in resolution.cross_validation_flags:
                        print(f"   • {flag}")
                
                print(f"\n{Colors.BOLD}🎯 Action Plan:{Colors.ENDC}")
                print(f"{resolution.final_plan}")
                
                print(f"\n{Colors.CYAN}💰 Cost:{Colors.ENDC} {resolution.metadata.get('estimated_cost', 'Unknown')}")
                print(f"{Colors.CYAN}⏱️  Timeline:{Colors.ENDC} {resolution.metadata.get('estimated_timeline', 'Unknown')}")
                print(f"{Colors.CYAN}⚠️  Risk:{Colors.ENDC} {resolution.metadata.get('risk_level', 'Unknown')}")
                
                # Save assistant response
                synthesis_text = f"""**Winning Strategy: {resolution.winning_specialist}**

{resolution.rationale}

**Action Plan:**
{resolution.final_plan}

**Metadata:**
- Cost: {resolution.metadata.get('estimated_cost', 'Unknown')}
- Timeline: {resolution.metadata.get('estimated_timeline', 'Unknown')}
- Risk: {resolution.metadata.get('risk_level', 'Unknown')}
"""
                db.save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=synthesis_text
                )
            
            print(f"{Colors.HEADER}{'─'*60}{Colors.ENDC}")
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.GREEN}👋 Strategy session interrupted.{Colors.ENDC}")
            break
        except Exception as e:
            print(f"\n{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")


async def run_free_mode_session(conversation_id: Optional[str] = None):
    """
    Run free discussion mode - no specialists, just casual conversation.
    Uses default agent for flexible chat.
    """
    print_welcome("free")
    
    # Determine conversation
    if conversation_id:
        print(f"{Colors.GREEN}Resuming conversation: {conversation_id}{Colors.ENDC}")
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        conv = db.create_conversation(title=f"Free Chat - {timestamp}")
        conversation_id = str(conv.id)
        print(f"{Colors.GREEN}Created new free discussion: {conversation_id}{Colors.ENDC}")
    
    # Use default agent for free chat
    config = get_default_config()
    agent = Agent(config=config, conversation_id=conversation_id)
    
    print(f"\n{Colors.CYAN}This is free discussion mode - talk about anything!{Colors.ENDC}")
    print(f"{Colors.CYAN}Type 'exit' to end session{Colors.ENDC}")
    print(f"{Colors.CYAN}Type '/strategic' to switch to War Room strategic mode{Colors.ENDC}")
    
    first_message = True
    
    while True:
        try:
            user_input = input(f"\n{Colors.BOLD}👤 You:{Colors.ENDC} ").strip()
            
            if not user_input:
                continue
            
            # Update conversation title
            if first_message:
                preview = user_input[:50] + "..." if len(user_input) > 50 else user_input
                db.client.table("conversations").update({
                    "title": f"{preview} - Free Chat"
                }).eq("id", conversation_id).execute()
                first_message = False
            
            # Handle commands
            if user_input.lower() in ["exit", "quit", "bye"]:
                print(f"\n{Colors.GREEN}👋 Free chat ended.{Colors.ENDC}")
                break
            
            if user_input.lower() == "/strategic":
                print(f"\n{Colors.WARNING}Switching to Strategic Mode...{Colors.ENDC}")
                await run_strategic_session(conversation_id)
                return
            
            # Run agent
            print(f"\n{Colors.CYAN}🤖 Thinking...{Colors.ENDC}", end="", flush=True)
            result = await agent.run_loop(user_input)
            print("\r" + " "*20 + "\r", end="")
            
            if result.get("success"):
                print(f"\n{Colors.GREEN}🤖 Assistant:{Colors.ENDC}")
                print(f"{Colors.HEADER}{'─'*60}{Colors.ENDC}")
                print(f"{result.get('output', '')}")
                print(f"{Colors.HEADER}{'─'*60}{Colors.ENDC}")
            else:
                print(f"\n{Colors.FAIL}❌ Error: {result.get('error')}{Colors.ENDC}")
        
        except KeyboardInterrupt:
            print(f"\n\n{Colors.GREEN}👋 Chat session interrupted.{Colors.ENDC}")
            break
        except Exception as e:
            print(f"\n{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")


def view_war_room_history():
    """View past War Room sessions."""
    print(f"\n{Colors.HEADER}--- War Room History ---{Colors.ENDC}")
    
    try:
        # Get War Room conversations
        convs = db.client.table("conversations").select("*").order("updated_at", desc=True).limit(20).execute()
        
        if not convs.data:
            print("No conversations found.")
            return
        
        print("\nRecent Sessions:")
        for i, conv in enumerate(convs.data, 1):
            title = conv.get('title', 'Untitled')
            created = conv.get('created_at', '')[:10]
            print(f"  [{i}] {title} - {created}")
        
        choice = input(f"\n{Colors.BOLD}Select session to resume (or 'b' for back):{Colors.ENDC} ").strip()
        
        if choice == 'b':
            return
        
        if choice.isdigit() and 1 <= int(choice) <= len(convs.data):
            conv = convs.data[int(choice)-1]
            conv_id = conv['id']
            title = conv['title']
            
            # Determine if strategic or free based on title
            if "War Room" in title or "Strategy" in title:
                asyncio.run(run_strategic_session(conversation_id=conv_id))
            else:
                asyncio.run(run_free_mode_session(conversation_id=conv_id))
        else:
            print("Invalid choice.")
    
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ Error: {e}{Colors.ENDC}")


def interactive_menu():
    """Main interactive menu."""
    while True:
        print(f"\n{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}{Colors.CYAN}WAR ROOM MAIN MENU{Colors.ENDC}")
        print(f"{Colors.HEADER}{'='*60}{Colors.ENDC}")
        print(f"\n  {Colors.BOLD}[1] Strategic Analysis{Colors.ENDC} - Multi-specialist conflict resolution")
        print(f"  {Colors.BOLD}[2] Free Discussion{Colors.ENDC} - Casual conversation mode")
        print(f"  {Colors.BOLD}[3] View History{Colors.ENDC} - Resume past sessions")
        print(f"  {Colors.BOLD}[4] Exit{Colors.ENDC}")
        
        choice = input(f"\n{Colors.BOLD}Select option:{Colors.ENDC} ").strip()
        
        if choice == '1':
            asyncio.run(run_strategic_session())
        
        elif choice == '2':
            asyncio.run(run_free_mode_session())
        
        elif choice == '3':
            view_war_room_history()
        
        elif choice == '4':
            print(f"\n{Colors.GREEN}👋 Goodbye!{Colors.ENDC}")
            break
        
        else:
            print(f"{Colors.FAIL}Invalid choice. Please try again.{Colors.ENDC}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="War Room V2.0 - Neural Boardroom CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive menu
  python -m agent_project.warroom_cli
  
  # Start strategic session
  python -m agent_project.warroom_cli --strategic
  
  # Start free discussion
  python -m agent_project.warroom_cli --free
  
  # Specific decision mode
  python -m agent_project.warroom_cli --strategic --mode GROWTH
        """
    )
    
    parser.add_argument(
        "--strategic",
        action="store_true",
        help="Start strategic analysis session"
    )
    
    parser.add_argument(
        "--free",
        action="store_true",
        help="Start free discussion mode"
    )
    
    parser.add_argument(
        "--mode",
        choices=["SPEED", "GROWTH", "SCALE"],
        help="Decision mode (for strategic sessions)"
    )
    
    args = parser.parse_args()
    
    # Direct execution modes
    if args.strategic:
        asyncio.run(run_strategic_session())
    elif args.free:
        asyncio.run(run_free_mode_session())
    else:
        # Default: show interactive menu
        interactive_menu()


if __name__ == "__main__":
    main()
