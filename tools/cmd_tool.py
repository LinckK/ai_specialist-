"""
Windows CMD command execution tool.
Executes commands safely and returns output.
SIMPLIFIED - No approval logic, permissions checked before execution in agent.py
"""

import subprocess
import os
from typing import Optional

def execute_cmd(command: str, working_dir: Optional[str] = None) -> str:
    """
    Execute a Windows CMD command and return the output.
    
    Args:
        command: The command to execute
        working_dir: Optional working directory (defaults to current)
        
    Returns:
        Command output or error message
    """
    print(f"\n--- Executing CMD command: '{command}' ---")
    
    try:
        # Set working directory
        cwd = working_dir if working_dir else os.getcwd()
        
        # Execute command
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        # Format output
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}"
        
        if result.returncode != 0:
            output += f"\n[Command exited with code {result.returncode}]"
        
        return output.strip() if output.strip() else "[Command executed successfully, no output]"
        
    except subprocess.TimeoutExpired:
        return f"Error: Command '{command}' timed out after 60 seconds"
    except Exception as e:
        return f"Error executing command: {e}"
