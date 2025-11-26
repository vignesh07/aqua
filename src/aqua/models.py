"""Data models for Aqua."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Any
import json


class AgentStatus(Enum):
    """Status of an agent in the quorum."""
    ACTIVE = "active"
    IDLE = "idle"
    DEAD = "dead"


class AgentType(Enum):
    """Type of AI agent."""
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    GENERIC = "generic"


class TaskStatus(Enum):
    """Status of a task."""
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass
class Agent:
    """An AI agent participating in the quorum."""
    id: str
    name: str
    agent_type: AgentType = AgentType.GENERIC
    pid: Optional[int] = None
    status: AgentStatus = AgentStatus.ACTIVE
    last_heartbeat_at: datetime = field(default_factory=datetime.utcnow)
    registered_at: datetime = field(default_factory=datetime.utcnow)
    current_task_id: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type.value,
            "pid": self.pid,
            "status": self.status.value,
            "last_heartbeat_at": self.last_heartbeat_at.isoformat(),
            "registered_at": self.registered_at.isoformat(),
            "current_task_id": self.current_task_id,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Agent":
        """Create Agent from database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            agent_type=AgentType(row["agent_type"]),
            pid=row["pid"],
            status=AgentStatus(row["status"]),
            last_heartbeat_at=datetime.fromisoformat(row["last_heartbeat_at"]),
            registered_at=datetime.fromisoformat(row["registered_at"]),
            current_task_id=row["current_task_id"],
            capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


@dataclass
class Task:
    """A work item to be claimed and executed."""
    id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    created_by: Optional[str] = None
    claimed_by: Optional[str] = None
    claim_term: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    tags: List[str] = field(default_factory=list)
    context: Optional[str] = None
    version: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority,
            "created_by": self.created_by,
            "claimed_by": self.claimed_by,
            "claim_term": self.claim_term,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "tags": self.tags,
            "context": self.context,
            "version": self.version,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Task":
        """Create Task from database row."""
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            created_by=row["created_by"],
            claimed_by=row["claimed_by"],
            claim_term=row["claim_term"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            claimed_at=datetime.fromisoformat(row["claimed_at"]) if row["claimed_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            result=row["result"],
            error=row["error"],
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            context=row["context"],
            version=row["version"],
        )


@dataclass
class Message:
    """A message between agents."""
    id: int
    from_agent: str
    to_agent: Optional[str]  # None = broadcast
    content: str
    message_type: str = "chat"
    created_at: datetime = field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "message_type": self.message_type,
            "created_at": self.created_at.isoformat(),
            "read_at": self.read_at.isoformat() if self.read_at else None,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Message":
        """Create Message from database row."""
        return cls(
            id=row["id"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            content=row["content"],
            message_type=row["message_type"],
            created_at=datetime.fromisoformat(row["created_at"]),
            read_at=datetime.fromisoformat(row["read_at"]) if row["read_at"] else None,
        )


@dataclass
class Leader:
    """Current leader information."""
    agent_id: str
    term: int
    lease_expires_at: datetime
    elected_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_id": self.agent_id,
            "term": self.term,
            "lease_expires_at": self.lease_expires_at.isoformat(),
            "elected_at": self.elected_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: dict) -> "Leader":
        """Create Leader from database row."""
        return cls(
            agent_id=row["agent_id"],
            term=row["term"],
            lease_expires_at=datetime.fromisoformat(row["lease_expires_at"]),
            elected_at=datetime.fromisoformat(row["elected_at"]),
        )

    def is_expired(self) -> bool:
        """Check if the leader's lease has expired."""
        return datetime.utcnow() > self.lease_expires_at


@dataclass
class Event:
    """An audit log event."""
    id: int
    timestamp: datetime
    event_type: str
    agent_id: Optional[str]
    task_id: Optional[str]
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "details": self.details,
        }

    @classmethod
    def from_row(cls, row: dict) -> "Event":
        """Create Event from database row."""
        return cls(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=row["event_type"],
            agent_id=row["agent_id"],
            task_id=row["task_id"],
            details=json.loads(row["details"]) if row["details"] else {},
        )
