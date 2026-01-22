from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID, uuid4

class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    email: str
    created_at: datetime = Field(default_factory=datetime.now)

class Conversation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: Optional[UUID] = None
    title: Optional[str] = "New Conversation"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None  # For assistant messages invoking tools
    tool_call_id: Optional[str] = None  # For tool output messages
    name: Optional[str] = None  # For tool output messages (function name)
    embedding: Optional[List[float]] = None  # Vector embedding for RAG
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentProfileDB(BaseModel):
    """Database representation of an Agent Profile"""
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    config: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)
