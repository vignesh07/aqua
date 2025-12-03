"""Database operations for Aqua."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Generator, Any

from aqua.models import Agent, Task, Message, Leader, Event, AgentStatus, TaskStatus

# Schema version for migrations
SCHEMA_VERSION = 3

SCHEMA = """
-- Enable WAL mode for concurrent access
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;

-- Agents table: registered participants
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    agent_type TEXT DEFAULT 'generic',
    pid INTEGER,
    status TEXT DEFAULT 'active',
    last_heartbeat_at TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    current_task_id TEXT,
    capabilities TEXT,
    metadata TEXT,
    last_progress TEXT,
    role TEXT
);

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_heartbeat ON agents(last_heartbeat_at);

-- Leader table: single row for leader election
CREATE TABLE IF NOT EXISTS leader (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    agent_id TEXT NOT NULL,
    term INTEGER NOT NULL,
    lease_expires_at TEXT NOT NULL,
    elected_at TEXT NOT NULL
);

-- Tasks table: work items
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 5,
    created_by TEXT,
    claimed_by TEXT,
    claim_term INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    claimed_at TEXT,
    completed_at TEXT,
    result TEXT,
    error TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    tags TEXT,
    context TEXT,
    version INTEGER DEFAULT 1,
    depends_on TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_claimed_by ON tasks(claimed_by);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC);

-- Messages table: inter-agent communication
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'chat',
    created_at TEXT NOT NULL,
    read_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent, read_at);
CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_agent);

-- Events table: audit log
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    agent_id TEXT,
    task_id TEXT,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

-- File locks table: prevent conflicts
CREATE TABLE IF NOT EXISTS file_locks (
    file_path TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    locked_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_file_locks_agent ON file_locks(agent_id);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""


class Database:
    """SQLite database wrapper with connection management."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                isolation_level=None,  # Autocommit by default
            )
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    @property
    def conn(self) -> sqlite3.Connection:
        """Get the database connection."""
        return self._get_connection()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self) -> None:
        """Initialize the database schema."""
        self.conn.executescript(SCHEMA)
        # Set schema version
        self.conn.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,)
        )

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for explicit transactions."""
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # =========================================================================
    # Agent Operations
    # =========================================================================

    def create_agent(self, agent: Agent) -> Agent:
        """Create a new agent."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO agents (id, name, agent_type, pid, status, last_heartbeat_at,
                              registered_at, current_task_id, capabilities, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent.id,
                agent.name,
                agent.agent_type.value,
                agent.pid,
                agent.status.value,
                now,
                now,
                agent.current_task_id,
                json.dumps(agent.capabilities),
                json.dumps(agent.metadata),
            ),
        )
        self.log_event("agent_joined", agent_id=agent.id, details={"name": agent.name})
        return agent

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        )
        row = cursor.fetchone()
        return Agent.from_row(dict(row)) if row else None

    def get_agent_by_name(self, name: str) -> Optional[Agent]:
        """Get an agent by name."""
        cursor = self.conn.execute(
            "SELECT * FROM agents WHERE name = ?", (name,)
        )
        row = cursor.fetchone()
        return Agent.from_row(dict(row)) if row else None

    def get_all_agents(self, status: Optional[AgentStatus] = None) -> List[Agent]:
        """Get all agents, optionally filtered by status."""
        if status:
            cursor = self.conn.execute(
                "SELECT * FROM agents WHERE status = ? ORDER BY registered_at",
                (status.value,)
            )
        else:
            cursor = self.conn.execute("SELECT * FROM agents ORDER BY registered_at")
        return [Agent.from_row(dict(row)) for row in cursor.fetchall()]

    def update_heartbeat(self, agent_id: str) -> None:
        """Update an agent's heartbeat timestamp."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            "UPDATE agents SET last_heartbeat_at = ? WHERE id = ?",
            (now, agent_id)
        )

    def update_agent_status(self, agent_id: str, status: AgentStatus) -> None:
        """Update an agent's status."""
        self.conn.execute(
            "UPDATE agents SET status = ? WHERE id = ?",
            (status.value, agent_id)
        )

    def update_agent_task(self, agent_id: str, task_id: Optional[str]) -> None:
        """Update an agent's current task."""
        self.conn.execute(
            "UPDATE agents SET current_task_id = ? WHERE id = ?",
            (task_id, agent_id)
        )

    def delete_agent(self, agent_id: str) -> None:
        """Delete an agent."""
        self.conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self.log_event("agent_left", agent_id=agent_id)

    # =========================================================================
    # Task Operations
    # =========================================================================

    def create_task(self, task: Task) -> Task:
        """Create a new task."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO tasks (id, title, description, status, priority, created_by,
                             claimed_by, claim_term, created_at, updated_at, claimed_at,
                             completed_at, result, error, retry_count, max_retries,
                             tags, context, version, depends_on)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.title,
                task.description,
                task.status.value,
                task.priority,
                task.created_by,
                task.claimed_by,
                task.claim_term,
                now,
                now,
                task.claimed_at.isoformat() if task.claimed_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                task.result,
                task.error,
                task.retry_count,
                task.max_retries,
                json.dumps(task.tags),
                task.context,
                task.version,
                json.dumps(task.depends_on) if task.depends_on else None,
            ),
        )
        self.log_event("task_created", task_id=task.id, details={"title": task.title})
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        cursor = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return Task.from_row(dict(row)) if row else None

    def get_all_tasks(
        self,
        status: Optional[TaskStatus] = None,
        claimed_by: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Task]:
        """Get all tasks with optional filters."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)
        if claimed_by:
            query += " AND claimed_by = ?"
            params.append(claimed_by)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

        query += " ORDER BY priority DESC, created_at ASC"

        cursor = self.conn.execute(query, params)
        return [Task.from_row(dict(row)) for row in cursor.fetchall()]

    def get_next_pending_task(self) -> Optional[Task]:
        """Get the next pending task (highest priority, oldest) with met dependencies."""
        # Get all pending tasks ordered by priority
        cursor = self.conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC
            """
        )
        rows = cursor.fetchall()

        for row in rows:
            task = Task.from_row(dict(row))
            if self._dependencies_met(task):
                return task

        return None

    def _dependencies_met(self, task: Task) -> bool:
        """Check if all dependencies of a task are complete."""
        if not task.depends_on:
            return True

        for dep_id in task.depends_on:
            dep_task = self.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.DONE:
                return False
        return True

    def get_blocking_dependencies(self, task: Task) -> List[Task]:
        """Get list of dependencies that are not yet complete."""
        blocking = []
        for dep_id in task.depends_on:
            dep_task = self.get_task(dep_id)
            if dep_task and dep_task.status != TaskStatus.DONE:
                blocking.append(dep_task)
        return blocking

    def claim_task(
        self, task_id: str, agent_id: str, term: int
    ) -> bool:
        """Atomically claim a task. Returns True if successful."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            UPDATE tasks
            SET status = 'claimed', claimed_by = ?, claimed_at = ?,
                claim_term = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (agent_id, now, term, now, task_id)
        )
        if cursor.rowcount == 1:
            self.log_event("task_claimed", agent_id=agent_id, task_id=task_id)
            return True
        return False

    def complete_task(
        self, task_id: str, agent_id: str, result: Optional[str] = None
    ) -> bool:
        """Mark a task as completed."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            UPDATE tasks
            SET status = 'done', completed_at = ?, result = ?, updated_at = ?
            WHERE id = ? AND claimed_by = ? AND status = 'claimed'
            """,
            (now, result, now, task_id, agent_id)
        )
        if cursor.rowcount == 1:
            self.log_event(
                "task_completed",
                agent_id=agent_id,
                task_id=task_id,
                details={"result": result}
            )
            return True
        return False

    def fail_task(
        self, task_id: str, agent_id: str, error: str
    ) -> bool:
        """Mark a task as failed."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            UPDATE tasks
            SET status = 'failed', error = ?, updated_at = ?,
                retry_count = retry_count + 1
            WHERE id = ? AND claimed_by = ? AND status = 'claimed'
            """,
            (error, now, task_id, agent_id)
        )
        if cursor.rowcount == 1:
            self.log_event(
                "task_failed",
                agent_id=agent_id,
                task_id=task_id,
                details={"error": error}
            )
            return True
        return False

    def abandon_task(self, task_id: str, reason: str = "abandoned") -> bool:
        """Mark a task as abandoned (e.g., agent died)."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            UPDATE tasks
            SET status = 'abandoned', claimed_by = NULL, error = ?,
                updated_at = ?, retry_count = retry_count + 1
            WHERE id = ? AND status = 'claimed'
            """,
            (reason, now, task_id)
        )
        if cursor.rowcount == 1:
            self.log_event("task_abandoned", task_id=task_id, details={"reason": reason})
            return True
        return False

    def requeue_abandoned_tasks(self) -> int:
        """Move abandoned tasks back to pending if under retry limit."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            UPDATE tasks
            SET status = 'pending', updated_at = ?
            WHERE status = 'abandoned' AND retry_count < max_retries
            """,
            (now,)
        )
        return cursor.rowcount

    def update_task_progress(self, task_id: str, context: str) -> bool:
        """Update task progress/context."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            UPDATE tasks SET context = ?, updated_at = ? WHERE id = ?
            """,
            (context, now, task_id)
        )
        return cursor.rowcount == 1

    def get_task_counts(self) -> dict:
        """Get counts of tasks by status."""
        cursor = self.conn.execute(
            """
            SELECT status, COUNT(*) as count FROM tasks GROUP BY status
            """
        )
        counts = {s.value: 0 for s in TaskStatus}
        for row in cursor.fetchall():
            counts[row["status"]] = row["count"]
        return counts

    # =========================================================================
    # Leader Operations
    # =========================================================================

    def get_leader(self) -> Optional[Leader]:
        """Get the current leader."""
        cursor = self.conn.execute("SELECT * FROM leader WHERE id = 1")
        row = cursor.fetchone()
        return Leader.from_row(dict(row)) if row else None

    def get_current_term(self) -> int:
        """Get the current leader term."""
        leader = self.get_leader()
        return leader.term if leader else 0

    def try_become_leader(self, agent_id: str, lease_seconds: int = 30) -> tuple[bool, int]:
        """
        Attempt to become or remain leader.
        Returns (is_leader, term).
        """
        from datetime import timedelta

        now = datetime.utcnow()
        new_lease_expires = (now + timedelta(seconds=lease_seconds)).isoformat()
        now_iso = now.isoformat()

        with self.transaction() as conn:
            cursor = conn.execute("SELECT * FROM leader WHERE id = 1")
            row = cursor.fetchone()

            if row is None:
                # No leader - become first
                conn.execute(
                    """
                    INSERT INTO leader (id, agent_id, term, lease_expires_at, elected_at)
                    VALUES (1, ?, 1, ?, ?)
                    """,
                    (agent_id, new_lease_expires, now_iso)
                )
                self.log_event(
                    "leader_elected",
                    agent_id=agent_id,
                    details={"term": 1, "reason": "first_leader"}
                )
                return (True, 1)

            current = Leader.from_row(dict(row))

            if current.lease_expires_at > now:
                # Lease still valid
                if current.agent_id == agent_id:
                    # I'm leader, renew lease
                    conn.execute(
                        "UPDATE leader SET lease_expires_at = ? WHERE id = 1",
                        (new_lease_expires,)
                    )
                    return (True, current.term)
                # Someone else is leader
                return (False, 0)

            # Lease expired - try to take over
            new_term = current.term + 1
            cursor = conn.execute(
                """
                UPDATE leader
                SET agent_id = ?, term = ?, lease_expires_at = ?, elected_at = ?
                WHERE id = 1 AND term = ?
                """,
                (agent_id, new_term, new_lease_expires, now_iso, current.term)
            )

            if cursor.rowcount == 1:
                self.log_event(
                    "leader_elected",
                    agent_id=agent_id,
                    details={
                        "term": new_term,
                        "reason": "lease_expired",
                        "previous_leader": current.agent_id
                    }
                )
                return (True, new_term)

            return (False, 0)

    # =========================================================================
    # Message Operations
    # =========================================================================

    def create_message(
        self,
        from_agent: str,
        content: str,
        to_agent: Optional[str] = None,
        message_type: str = "chat",
    ) -> Message:
        """Create a new message."""
        now = datetime.utcnow().isoformat()
        cursor = self.conn.execute(
            """
            INSERT INTO messages (from_agent, to_agent, content, message_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (from_agent, to_agent, content, message_type, now)
        )
        msg_id = cursor.lastrowid
        return Message(
            id=msg_id,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            message_type=message_type,
            created_at=datetime.fromisoformat(now),
            read_at=None,
        )

    def get_messages(
        self,
        to_agent: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Message]:
        """Get messages for an agent."""
        query = "SELECT * FROM messages WHERE 1=1"
        params: List[Any] = []

        if to_agent:
            # Get messages to this agent OR broadcasts
            query += " AND (to_agent = ? OR to_agent IS NULL)"
            params.append(to_agent)

        if unread_only:
            query += " AND read_at IS NULL"

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        return [Message.from_row(dict(row)) for row in cursor.fetchall()]

    def mark_messages_read(self, agent_id: str, message_ids: List[int]) -> int:
        """Mark messages as read."""
        if not message_ids:
            return 0
        now = datetime.utcnow().isoformat()
        placeholders = ",".join("?" * len(message_ids))
        cursor = self.conn.execute(
            f"""
            UPDATE messages SET read_at = ?
            WHERE id IN ({placeholders}) AND (to_agent = ? OR to_agent IS NULL)
            """,
            [now] + message_ids + [agent_id]
        )
        return cursor.rowcount

    # =========================================================================
    # Event Log Operations
    # =========================================================================

    def log_event(
        self,
        event_type: str,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Log an event."""
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO events (timestamp, event_type, agent_id, task_id, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            (now, event_type, agent_id, task_id, json.dumps(details) if details else None)
        )

    def get_events(
        self,
        event_type: Optional[str] = None,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get events with optional filters."""
        query = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if task_id:
            query += " AND task_id = ?"
            params.append(task_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(query, params)
        return [Event.from_row(dict(row)) for row in cursor.fetchall()]

    # =========================================================================
    # File Lock Operations
    # =========================================================================

    def lock_file(self, file_path: str, agent_id: str) -> bool:
        """Lock a file for exclusive access. Returns True if successful."""
        now = datetime.utcnow().isoformat()
        try:
            self.conn.execute(
                """
                INSERT INTO file_locks (file_path, agent_id, locked_at)
                VALUES (?, ?, ?)
                """,
                (file_path, agent_id, now)
            )
            self.log_event("file_locked", agent_id=agent_id, details={"file": file_path})
            return True
        except sqlite3.IntegrityError:
            # Already locked
            return False

    def unlock_file(self, file_path: str, agent_id: str) -> bool:
        """Unlock a file. Only the locking agent can unlock."""
        cursor = self.conn.execute(
            "DELETE FROM file_locks WHERE file_path = ? AND agent_id = ?",
            (file_path, agent_id)
        )
        if cursor.rowcount == 1:
            self.log_event("file_unlocked", agent_id=agent_id, details={"file": file_path})
            return True
        return False

    def get_file_lock(self, file_path: str) -> Optional[dict]:
        """Get lock info for a file."""
        cursor = self.conn.execute(
            "SELECT * FROM file_locks WHERE file_path = ?",
            (file_path,)
        )
        row = cursor.fetchone()
        if row:
            return {"file_path": row["file_path"], "agent_id": row["agent_id"], "locked_at": row["locked_at"]}
        return None

    def get_all_locks(self) -> List[dict]:
        """Get all file locks."""
        cursor = self.conn.execute("SELECT * FROM file_locks ORDER BY locked_at DESC")
        return [{"file_path": row["file_path"], "agent_id": row["agent_id"], "locked_at": row["locked_at"]}
                for row in cursor.fetchall()]

    def get_agent_locks(self, agent_id: str) -> List[dict]:
        """Get all files locked by an agent."""
        cursor = self.conn.execute(
            "SELECT * FROM file_locks WHERE agent_id = ? ORDER BY locked_at DESC",
            (agent_id,)
        )
        return [{"file_path": row["file_path"], "agent_id": row["agent_id"], "locked_at": row["locked_at"]}
                for row in cursor.fetchall()]

    def release_agent_locks(self, agent_id: str) -> int:
        """Release all locks held by an agent. Returns count released."""
        cursor = self.conn.execute(
            "DELETE FROM file_locks WHERE agent_id = ?",
            (agent_id,)
        )
        return cursor.rowcount


def get_db(project_dir: Path) -> Database:
    """Get database instance for a project."""
    aqua_dir = project_dir / ".aqua"
    db_path = aqua_dir / "aqua.db"
    db = Database(db_path)

    # Run migrations if needed
    _run_migrations(db)

    return db


def _run_migrations(db: Database) -> None:
    """Run any pending database migrations."""
    try:
        cursor = db.conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        current_version = row["version"] if row else 0
    except Exception:
        # Table doesn't exist yet
        return

    # Migration from v1 to v2: add last_progress and role columns to agents
    if current_version < 2:
        try:
            db.conn.execute("ALTER TABLE agents ADD COLUMN last_progress TEXT")
        except Exception:
            pass  # Column might already exist
        try:
            db.conn.execute("ALTER TABLE agents ADD COLUMN role TEXT")
        except Exception:
            pass  # Column might already exist
        db.conn.execute("UPDATE schema_version SET version = 2")
        current_version = 2

    # Migration from v2 to v3: add depends_on column to tasks
    if current_version < 3:
        try:
            db.conn.execute("ALTER TABLE tasks ADD COLUMN depends_on TEXT")
        except Exception:
            pass  # Column might already exist
        db.conn.execute("UPDATE schema_version SET version = 3")


def init_db(project_dir: Path) -> Database:
    """Initialize database for a project."""
    aqua_dir = project_dir / ".aqua"
    aqua_dir.mkdir(mode=0o755, exist_ok=True)

    # Create sessions directory for per-terminal agent tracking
    sessions_dir = aqua_dir / "sessions"
    sessions_dir.mkdir(mode=0o755, exist_ok=True)

    db = get_db(project_dir)
    db.init_schema()
    return db
