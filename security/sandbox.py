import os
from pathlib import Path
from typing import Union

class Sandbox:
    """
    Security Sandbox for File Operations.
    
    Rules:
    1. READ: Allowed in the entire workspace root (to access projects, documents, etc).
    2. WRITE: Restricted EXCLUSIVELY to:
       - ./agent_archives/
       - ./n8n_output/
    3. Path Traversal: Strictly blocked (../).
    """
    
    # Define the workspace root (assuming this code runs inside the workspace)
    WORKSPACE_ROOT = Path(os.getcwd()).resolve()
    
    # Define allowed write directories relative to root
    ALLOWED_WRITE_DIRS = [
        WORKSPACE_ROOT / "agent_archives",
        WORKSPACE_ROOT / "n8n_output"
    ]

    @staticmethod
    def validate_path(path: Union[str, Path], operation: str = "read") -> Path:
        """
        Validates a path against the sandbox rules.
        
        Args:
            path: The path to validate.
            operation: "read" or "write".
            
        Returns:
            The resolved absolute Path object if valid.
            
        Raises:
            PermissionError: If the path violates sandbox rules.
        """
        try:
            # Resolve path to absolute
            target_path = (Sandbox.WORKSPACE_ROOT / path).resolve()
        except Exception as e:
            raise PermissionError(f"Invalid path format: {e}")

        # Rule 0: Path Traversal Check
        # Ensure the target path is inside the Workspace Root
        # This prevents ../../../Windows/System32 attacks
        if not str(target_path).startswith(str(Sandbox.WORKSPACE_ROOT)):
             raise PermissionError(f"Security Violation: Access denied to path outside workspace: {target_path}")

        # Rule 1: READ Operation
        if operation == "read":
            # Read is allowed anywhere inside the workspace
            return target_path

        # Rule 2: WRITE Operation
        elif operation == "write":
            # Write is strictly limited to allowed directories
            is_allowed = False
            for allowed_dir in Sandbox.ALLOWED_WRITE_DIRS:
                # Check if target_path is inside or is the allowed_dir
                if str(target_path).startswith(str(allowed_dir)):
                    is_allowed = True
                    break
            
            if not is_allowed:
                raise PermissionError(
                    f"Security Violation: Write access denied to {target_path}. "
                    f"Writes are only allowed in: {[d.name for d in Sandbox.ALLOWED_WRITE_DIRS]}"
                )
            
            return target_path

        else:
            raise ValueError(f"Unknown operation: {operation}")

    @staticmethod
    def ensure_write_dirs_exist():
        """Ensures the allowed write directories exist."""
        for d in Sandbox.ALLOWED_WRITE_DIRS:
            d.mkdir(parents=True, exist_ok=True)
