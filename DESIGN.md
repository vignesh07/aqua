# Aqua Design Document

**Autonomous QUorum of Agents**

Version: 1.0.0
Status: Design Complete
Author: Vignesh
Date: 2025-01-25

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [System Architecture](#system-architecture)
5. [Data Model](#data-model)
6. [Core Algorithms](#core-algorithms)
7. [CLI Interface](#cli-interface)
8. [Agent Integration Protocol](#agent-integration-protocol)
9. [Failure Handling](#failure-handling)
10. [Configuration](#configuration)
11. [Security Considerations](#security-considerations)
12. [Future Extensions](#future-extensions)
13. [Appendix](#appendix)

---

## Executive Summary

Aqua is a lightweight, agent-agnostic coordination system for CLI-based AI agents. It enables multiple AI agents (Claude Code, Codex, Gemini CLI, or any CLI tool) running in separate terminal sessions to collaborate on tasks within a shared codebase.

**Key capabilities:**
- **Leader Election**: Automatic coordination with one agent assuming leadership
- **Task Management**: Shared task queue with atomic claiming and status tracking
- **Message Passing**: Inter-agent communication via broadcast or direct messages
- **Crash Recovery**: Automatic detection of dead agents and task reassignment

**Design principles:**
- Zero external services (no Redis, Docker, or external databases)
- Agent-agnostic protocol (works with any CLI agent)
- Single `pip install` deployment
- Fun and intuitive to use

---

## Problem Statement

### The Challenge

Modern AI coding assistants like Claude Code, OpenAI Codex, and Google Gemini CLI are powerful individually, but there's no standard way to coordinate multiple instances working on the same codebase. Users who want to parallelize work across multiple AI agents face several challenges:

1. **No coordination**: Agents don't know about each other and may work on the same files
2. **No task distribution**: Manual assignment of work to each agent
3. **No communication**: Agents can't ask each other for help or share context
4. **No failure recovery**: If an agent crashes, its work is lost

### Use Cases

1. **Parallel Feature Development**: Multiple agents work on different features simultaneously
2. **Division of Labor**: One agent writes code while another writes tests
3. **Review and Verification**: Leader agent reviews work done by follower agents
4. **Large Refactoring**: Coordinate changes across many files without conflicts

### Why Not Existing Solutions?

| Solution | Why Not Suitable |
|----------|------------------|
| Redis/Message Queue | External dependency, complex setup |
| Kubernetes/Docker | Overkill for local CLI coordination |
| File locks | Race conditions, no task management |
| Database servers | Heavy, requires running services |

Aqua fills this gap with a lightweight, file-based solution using SQLite.

---

## Goals and Non-Goals

### Goals

1. **G1**: Enable multiple CLI AI agents to coordinate on a shared codebase
2. **G2**: Provide automatic leader election with crash recovery
3. **G3**: Support atomic task claiming to prevent duplicate work
4. **G4**: Enable inter-agent communication
5. **G5**: Work with any CLI agent (agent-agnostic protocol)
6. **G6**: Zero external dependencies beyond pip packages
7. **G7**: Simple installation: `pip install aqua-coord`
8. **G8**: Intuitive CLI that's fun to use

### Non-Goals

1. **NG1**: Distributed coordination across multiple machines (local only)
2. **NG2**: Real-time streaming (polling-based is sufficient)
3. **NG3**: Authentication/authorization (trust local processes)
4. **NG4**: GUI interface (CLI-first)
5. **NG5**: Agent-specific integrations (protocol is generic)
6. **NG6**: Persistent agent sessions across reboots

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          User's Terminal(s)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Terminal 1 │  │  Terminal 2 │  │  Terminal 3 │                 │
│  │  Claude Code│  │  Codex CLI  │  │  Gemini CLI │                 │
│  │  (Leader)   │  │  (Follower) │  │  (Follower) │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Aqua CLI (aqua)                         │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │   │
│  │  │  init   │ │  add    │ │  join   │ │  claim  │  ...      │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                    Coordinator Core                          │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │   │
│  │  │    Leader    │ │     Task     │ │   Message    │        │   │
│  │  │   Election   │ │   Scheduler  │ │   Passing    │        │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘        │   │
│  └──────────────────────────┬──────────────────────────────────┘   │
│                             │                                       │
│  ┌──────────────────────────▼──────────────────────────────────┐   │
│  │                   SQLite Database                            │   │
│  │                 .aqua/aqua.db (WAL mode)                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│                        Project Directory                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Overview

#### 1. Aqua CLI (`aqua`)

The user-facing command-line interface built with Click. Provides commands for:
- Project initialization (`init`)
- Task management (`add`, `list`, `status`)
- Agent lifecycle (`join`, `leave`)
- Task operations (`claim`, `done`, `fail`, `progress`)
- Communication (`msg`, `inbox`)
- Monitoring (`watch`, `doctor`, `log`)

#### 2. Coordinator Core

The business logic layer containing:

- **Leader Election**: Lease-based algorithm with fencing tokens
- **Task Scheduler**: Priority-based task queue with atomic claiming
- **Message Passing**: Pub/sub style messaging between agents

#### 3. SQLite Database

Persistent storage using SQLite in WAL (Write-Ahead Logging) mode for concurrent access. Located at `.aqua/aqua.db` within the project directory.

### File Structure

```
aqua/                           # Repository root
├── pyproject.toml              # Package configuration
├── README.md                   # User documentation
├── DESIGN.md                   # This document
├── LICENSE                     # MIT License
│
├── src/
│   └── aqua/
│       ├── __init__.py         # Package version, exports
│       ├── __main__.py         # Entry point: python -m aqua
│       ├── cli.py              # Click CLI definitions
│       ├── db.py               # SQLite operations, schema
│       ├── models.py           # Dataclasses: Task, Agent, Message
│       ├── leader.py           # Leader election algorithm
│       ├── coordinator.py      # Task claiming, recovery
│       └── utils.py            # Helpers (names, time, process)
│
└── tests/
    ├── conftest.py             # Pytest fixtures
    ├── test_db.py              # Database tests
    ├── test_leader.py          # Leader election tests
    ├── test_tasks.py           # Task operations tests
    └── test_integration.py     # Multi-agent scenarios

# Per-project Aqua directory (created by `aqua init`)
.aqua/
├── aqua.db                     # SQLite database
├── aqua.db-wal                 # WAL file (auto-created)
├── aqua.db-shm                 # Shared memory file (auto-created)
├── config.yaml                 # Optional configuration
└── logs/                       # Optional log directory
```

### Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.10+ | Universal, easy to install, good CLI support |
| CLI Framework | Click | Better than argparse, widely used, good UX |
| Terminal UI | Rich | Beautiful tables, colors, live displays |
| Database | SQLite (WAL) | Zero setup, built into Python, ACID compliant |
| Package Format | pip/PyPI | Standard Python distribution |

---

## Data Model

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Agents    │       │    Tasks    │       │  Messages   │
├─────────────┤       ├─────────────┤       ├─────────────┤
│ id (PK)     │──┐    │ id (PK)     │       │ id (PK)     │
│ name        │  │    │ title       │       │ from_agent  │──┐
│ agent_type  │  │    │ description │       │ to_agent    │  │
│ pid         │  │    │ status      │       │ content     │  │
│ status      │  ├───▶│ priority    │       │ message_type│  │
│ last_hb_at  │  │    │ created_by  │◀──────│ created_at  │  │
│ registered  │  │    │ claimed_by  │       │ read_at     │  │
│ current_task│──┘    │ claim_term  │       └─────────────┘  │
│ capabilities│       │ created_at  │              │         │
│ metadata    │       │ updated_at  │              │         │
└─────────────┘       │ ...         │              │         │
       │              └─────────────┘              │         │
       │                                           │         │
       │              ┌─────────────┐              │         │
       │              │   Leader    │              │         │
       │              ├─────────────┤              │         │
       └─────────────▶│ id (=1)     │◀─────────────┘         │
                      │ agent_id    │                        │
                      │ term        │                        │
                      │ lease_exp   │                        │
                      │ elected_at  │                        │
                      └─────────────┘                        │
                                                             │
                      ┌─────────────┐                        │
                      │   Events    │                        │
                      ├─────────────┤                        │
                      │ id (PK)     │                        │
                      │ timestamp   │                        │
                      │ event_type  │◀───────────────────────┘
                      │ agent_id    │
                      │ task_id     │
                      │ details     │
                      └─────────────┘
```

### Database Schema

```sql
-- Enable WAL mode for concurrent access
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;

-- ============================================
-- AGENTS TABLE
-- ============================================
-- Registered agents participating in the quorum
CREATE TABLE agents (
    id TEXT PRIMARY KEY,              -- Short UUID (8 chars): "a1b2c3d4"
    name TEXT NOT NULL UNIQUE,        -- Human-readable: "claude-main"
    agent_type TEXT DEFAULT 'generic',-- Type: claude, codex, gemini, generic
    pid INTEGER,                      -- OS process ID for crash detection
    status TEXT DEFAULT 'active',     -- active, idle, dead
    last_heartbeat_at TEXT NOT NULL,  -- ISO8601: "2025-01-25T10:30:00.000"
    registered_at TEXT NOT NULL,      -- When agent joined
    current_task_id TEXT,             -- Currently claimed task (FK to tasks.id)
    capabilities TEXT,                -- JSON array: ["code", "test", "docs"]
    metadata TEXT,                    -- JSON blob for agent-specific data

    CONSTRAINT valid_status CHECK (status IN ('active', 'idle', 'dead')),
    CONSTRAINT valid_type CHECK (agent_type IN ('claude', 'codex', 'gemini', 'generic'))
);

CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_heartbeat ON agents(last_heartbeat_at);

-- ============================================
-- LEADER TABLE
-- ============================================
-- Single-row table for leader election
CREATE TABLE leader (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Enforces single row
    agent_id TEXT NOT NULL,                 -- Current leader's agent ID
    term INTEGER NOT NULL,                  -- Fencing token (monotonic)
    lease_expires_at TEXT NOT NULL,         -- When lease expires
    elected_at TEXT NOT NULL,               -- When current term started

    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- ============================================
-- TASKS TABLE
-- ============================================
-- Work items to be claimed and executed
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,              -- Short UUID: "t1b2c3d4"
    title TEXT NOT NULL,              -- Brief description
    description TEXT,                 -- Detailed description
    status TEXT DEFAULT 'pending',    -- pending, claimed, done, failed, abandoned
    priority INTEGER DEFAULT 5,       -- 1-10, higher = more important

    -- Ownership tracking
    created_by TEXT,                  -- Agent ID that created this task
    claimed_by TEXT,                  -- Agent ID currently working on it
    claim_term INTEGER,               -- Leader term when claimed (fencing)

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    claimed_at TEXT,
    completed_at TEXT,

    -- Results
    result TEXT,                      -- Completion summary (JSON)
    error TEXT,                       -- Failure reason

    -- Retry handling
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Metadata
    tags TEXT,                        -- JSON array: ["frontend", "urgent"]
    context TEXT,                     -- Additional context for the agent
    version INTEGER DEFAULT 1,        -- Optimistic concurrency control

    CONSTRAINT valid_status CHECK (status IN ('pending', 'claimed', 'done', 'failed', 'abandoned')),
    CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 10),
    FOREIGN KEY (created_by) REFERENCES agents(id),
    FOREIGN KEY (claimed_by) REFERENCES agents(id)
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_claimed_by ON tasks(claimed_by);
CREATE INDEX idx_tasks_priority ON tasks(priority DESC, created_at ASC);

-- ============================================
-- MESSAGES TABLE
-- ============================================
-- Inter-agent communication
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,         -- Sender agent ID
    to_agent TEXT,                    -- Recipient: agent_id, NULL (broadcast), @leader, @idle
    content TEXT NOT NULL,            -- Message content
    message_type TEXT DEFAULT 'chat', -- chat, request, response, system
    created_at TEXT NOT NULL,
    read_at TEXT,                     -- When recipient read it (NULL = unread)

    CONSTRAINT valid_type CHECK (message_type IN ('chat', 'request', 'response', 'system')),
    FOREIGN KEY (from_agent) REFERENCES agents(id)
);

CREATE INDEX idx_messages_to ON messages(to_agent, read_at);
CREATE INDEX idx_messages_from ON messages(from_agent);

-- ============================================
-- EVENTS TABLE
-- ============================================
-- Audit log for debugging and observability
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    event_type TEXT NOT NULL,         -- leader_elected, task_claimed, agent_died, etc.
    agent_id TEXT,                    -- Related agent (if applicable)
    task_id TEXT,                     -- Related task (if applicable)
    details TEXT                      -- JSON blob with event-specific data
);

CREATE INDEX idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX idx_events_type ON events(event_type);
```

### Data Classes (Python)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum

class AgentStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    DEAD = "dead"

class AgentType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"
    GENERIC = "generic"

class TaskStatus(Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    FAILED = "failed"
    ABANDONED = "abandoned"

@dataclass
class Agent:
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

@dataclass
class Task:
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

@dataclass
class Message:
    id: int
    from_agent: str
    to_agent: Optional[str]  # None = broadcast
    content: str
    message_type: str = "chat"
    created_at: datetime = field(default_factory=datetime.utcnow)
    read_at: Optional[datetime] = None

@dataclass
class Leader:
    agent_id: str
    term: int
    lease_expires_at: datetime
    elected_at: datetime
```

---

## Core Algorithms

### Leader Election

Aqua uses a **lease-based leader election** algorithm with **fencing tokens** to prevent split-brain scenarios.

#### Key Concepts

1. **Lease**: A time-limited lock on leadership (default: 30 seconds)
2. **Term**: A monotonically increasing number that changes each election (fencing token)
3. **Heartbeat**: Leader must renew lease before it expires

#### Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│                    Leader Election Flow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Agent starts                                                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐     Yes    ┌─────────────────────┐             │
│  │ Leader row  │───────────▶│ Is lease expired?   │             │
│  │ exists?     │            └──────────┬──────────┘             │
│  └──────┬──────┘                       │                        │
│         │ No                     No    │    Yes                  │
│         ▼                        │     ▼                        │
│  ┌─────────────┐            ┌────┴────┐ ┌─────────────┐        │
│  │ INSERT with │            │ Am I    │ │ Try UPDATE  │        │
│  │ term = 1    │            │ leader? │ │ with term+1 │        │
│  └──────┬──────┘            └────┬────┘ └──────┬──────┘        │
│         │                        │             │                │
│         ▼                   Yes  │             ▼                │
│  ┌─────────────┐            │    │      ┌─────────────┐        │
│  │ I am leader │◀───────────┘    │      │ rowcount=1? │        │
│  │ (term 1)    │                 │      └──────┬──────┘        │
│  └─────────────┘                 │        Yes  │  No           │
│                                  ▼             ▼    │          │
│                           ┌─────────────┐  ┌───────────┐       │
│                           │ Renew lease │  │ I am      │       │
│                           │ (same term) │  │ leader    │       │
│                           └─────────────┘  │ (new term)│       │
│                                            └───────────┘       │
│                                                  │              │
│                                                  ▼              │
│                                           ┌───────────┐        │
│                                           │ I am      │        │
│                                           │ follower  │◀───────┤
│                                           └───────────┘        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

```python
from datetime import datetime, timedelta
from typing import Tuple
import sqlite3

LEASE_DURATION = timedelta(seconds=30)

def try_become_leader(agent_id: str, conn: sqlite3.Connection) -> Tuple[bool, int]:
    """
    Attempt to become or remain leader.

    Returns:
        (is_leader: bool, term: int)
        - If is_leader is True, term is the current term we're leading
        - If is_leader is False, term is 0
    """
    now = datetime.utcnow()
    new_lease_expires = (now + LEASE_DURATION).isoformat()
    now_iso = now.isoformat()

    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE")  # Get write lock immediately

        # Check current leader state
        cursor.execute("SELECT agent_id, term, lease_expires_at FROM leader WHERE id = 1")
        row = cursor.fetchone()

        if row is None:
            # No leader exists - try to become first leader
            cursor.execute("""
                INSERT INTO leader (id, agent_id, term, lease_expires_at, elected_at)
                VALUES (1, ?, 1, ?, ?)
            """, (agent_id, new_lease_expires, now_iso))
            conn.commit()
            log_event(conn, 'leader_elected', agent_id, {'term': 1, 'reason': 'first_leader'})
            return (True, 1)

        current_leader_id, current_term, lease_expires_str = row
        lease_expires = datetime.fromisoformat(lease_expires_str)

        if lease_expires > now:
            # Lease still valid
            if current_leader_id == agent_id:
                # I'm the current leader - renew my lease
                cursor.execute("""
                    UPDATE leader SET lease_expires_at = ? WHERE id = 1
                """, (new_lease_expires,))
                conn.commit()
                return (True, current_term)
            else:
                # Someone else is leader
                conn.rollback()
                return (False, 0)

        # Lease expired - try to take over with incremented term
        new_term = current_term + 1
        cursor.execute("""
            UPDATE leader
            SET agent_id = ?, term = ?, lease_expires_at = ?, elected_at = ?
            WHERE id = 1 AND term = ?
        """, (agent_id, new_term, new_lease_expires, now_iso, current_term))

        if cursor.rowcount == 1:
            conn.commit()
            log_event(conn, 'leader_elected', agent_id, {
                'term': new_term,
                'reason': 'lease_expired',
                'previous_leader': current_leader_id
            })
            return (True, new_term)
        else:
            # Someone else won the race
            conn.rollback()
            return (False, 0)

    except Exception:
        conn.rollback()
        raise
```

#### Fencing Tokens

The `term` field acts as a fencing token. When a leader performs any operation that modifies shared state, it includes its term. The database rejects operations from stale terms:

```python
def claim_task_as_leader(agent_id: str, task_id: str, my_term: int, conn):
    """Leader assigns a task - includes term for fencing."""
    cursor = conn.cursor()

    # Only succeed if we're still the current leader (term matches)
    cursor.execute("""
        UPDATE tasks
        SET status = 'claimed', claimed_by = ?, claim_term = ?
        WHERE id = ?
        AND status = 'pending'
        AND ? = (SELECT term FROM leader WHERE id = 1)
    """, (agent_id, my_term, task_id, my_term))

    return cursor.rowcount == 1
```

#### Why This Works

1. **No Split Brain**: Only one agent can hold a valid lease at any time
2. **Crash Recovery**: If leader crashes, lease expires and new leader is elected
3. **Zombie Prevention**: Fencing tokens prevent stale leaders from making changes
4. **No External Dependencies**: Pure SQLite with atomic transactions

### Task Claiming

Task claiming must be atomic to prevent two agents from claiming the same task.

#### Algorithm

```python
def claim_task(
    agent_id: str,
    task_id: str = None,
    conn: sqlite3.Connection
) -> Optional[Task]:
    """
    Atomically claim a task.

    Args:
        agent_id: The agent claiming the task
        task_id: Specific task to claim, or None for next available
        conn: Database connection

    Returns:
        The claimed Task, or None if no task available/claim failed
    """
    now = datetime.utcnow().isoformat()
    cursor = conn.cursor()

    # Get current term for fencing
    cursor.execute("SELECT term FROM leader WHERE id = 1")
    row = cursor.fetchone()
    current_term = row[0] if row else 0

    try:
        cursor.execute("BEGIN IMMEDIATE")

        if task_id:
            # Claim specific task
            target_id = task_id
        else:
            # Find next available task (highest priority, oldest)
            cursor.execute("""
                SELECT id FROM tasks
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return None
            target_id = row[0]

        # Atomic claim: only succeeds if still pending
        cursor.execute("""
            UPDATE tasks
            SET status = 'claimed',
                claimed_by = ?,
                claimed_at = ?,
                claim_term = ?,
                updated_at = ?
            WHERE id = ? AND status = 'pending'
        """, (agent_id, now, current_term, now, target_id))

        if cursor.rowcount == 0:
            # Task was claimed by someone else
            conn.rollback()
            return None

        # Update agent's current task
        cursor.execute("""
            UPDATE agents SET current_task_id = ? WHERE id = ?
        """, (target_id, agent_id))

        conn.commit()

        # Fetch and return the claimed task
        return get_task(target_id, conn)

    except Exception:
        conn.rollback()
        raise
```

#### Optimistic Concurrency

For task updates (not claiming), we use optimistic concurrency with version numbers:

```python
def update_task_progress(
    task_id: str,
    progress: str,
    expected_version: int,
    conn: sqlite3.Connection
) -> bool:
    """Update task progress with optimistic locking."""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks
        SET context = ?, updated_at = ?, version = version + 1
        WHERE id = ? AND version = ?
    """, (progress, datetime.utcnow().isoformat(), task_id, expected_version))

    if cursor.rowcount == 0:
        raise ConcurrencyError(f"Task {task_id} was modified by another agent")

    conn.commit()
    return True
```

### Crash Detection and Recovery

The leader is responsible for detecting crashed agents and recovering their tasks.

#### Detection Mechanisms

1. **Heartbeat Timeout**: Agent's `last_heartbeat_at` older than threshold (60 seconds)
2. **Process Check**: Verify PID is still running via `os.kill(pid, 0)`

#### Recovery Algorithm

```python
import os

DEAD_THRESHOLD = timedelta(seconds=60)

def process_exists(pid: int) -> bool:
    """Check if a process exists without killing it."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def recover_dead_agents(conn: sqlite3.Connection) -> List[str]:
    """
    Find crashed agents, mark them dead, and release their tasks.

    Returns:
        List of recovered agent IDs
    """
    now = datetime.utcnow()
    stale_threshold = (now - DEAD_THRESHOLD).isoformat()
    recovered = []

    cursor = conn.cursor()

    # Find potentially dead agents
    cursor.execute("""
        SELECT id, pid, name FROM agents
        WHERE status = 'active' AND last_heartbeat_at < ?
    """, (stale_threshold,))
    stale_agents = cursor.fetchall()

    for agent_id, pid, name in stale_agents:
        # Double-check: is the process actually dead?
        if pid and process_exists(pid):
            # Process alive but not heartbeating - might be stuck
            # Log warning but don't kill
            log_event(conn, 'agent_unresponsive', agent_id, {
                'pid': pid,
                'last_heartbeat': stale_threshold
            })
            continue

        # Agent is dead - recover
        cursor.execute("BEGIN IMMEDIATE")
        try:
            # Mark agent as dead
            cursor.execute("""
                UPDATE agents SET status = 'dead' WHERE id = ?
            """, (agent_id,))

            # Release their claimed tasks (make reclaimable)
            cursor.execute("""
                UPDATE tasks
                SET status = 'abandoned',
                    claimed_by = NULL,
                    retry_count = retry_count + 1,
                    updated_at = ?,
                    error = 'Agent died while processing'
                WHERE claimed_by = ? AND status = 'claimed'
            """, (now.isoformat(), agent_id))
            released_count = cursor.rowcount

            # Log the event
            log_event(conn, 'agent_died', agent_id, {
                'reason': 'heartbeat_timeout',
                'pid': pid,
                'tasks_released': released_count
            })

            conn.commit()
            recovered.append(agent_id)

        except Exception:
            conn.rollback()
            raise

    return recovered
```

#### Task Retry Logic

Abandoned tasks can be reclaimed if under retry limit:

```python
def get_reclaimable_tasks(conn: sqlite3.Connection) -> List[Task]:
    """Get tasks that can be reclaimed after being abandoned."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM tasks
        WHERE status = 'abandoned' AND retry_count < max_retries
        ORDER BY priority DESC, created_at ASC
    """)

    return [row_to_task(row) for row in cursor.fetchall()]

def reclaim_abandoned_task(task_id: str, conn: sqlite3.Connection):
    """Move an abandoned task back to pending for reclaim."""
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tasks
        SET status = 'pending', updated_at = ?
        WHERE id = ? AND status = 'abandoned' AND retry_count < max_retries
    """, (datetime.utcnow().isoformat(), task_id))

    conn.commit()
```

### Heartbeat System

Aqua supports two heartbeat modes:

#### 1. Implicit Heartbeat (Default)

Every CLI command updates the agent's heartbeat automatically:

```python
def with_heartbeat(func):
    """Decorator that updates heartbeat on every command."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ctx = click.get_current_context()
        agent_id = ctx.obj.get('agent_id')

        if agent_id:
            update_heartbeat(agent_id, ctx.obj['db'])

        return func(*args, **kwargs)
    return wrapper

def update_heartbeat(agent_id: str, conn: sqlite3.Connection):
    """Update agent's last heartbeat timestamp."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE agents SET last_heartbeat_at = ? WHERE id = ?
    """, (datetime.utcnow().isoformat(), agent_id))
    conn.commit()
```

#### 2. Daemon Mode (Optional)

For real-time features, run `aqua daemon`:

```python
async def daemon_loop(agent_id: str, conn: sqlite3.Connection):
    """Background loop for heartbeat and recovery."""
    while True:
        try:
            # Update my heartbeat
            update_heartbeat(agent_id, conn)

            # If I'm leader, do recovery
            is_leader, term = try_become_leader(agent_id, conn)
            if is_leader:
                recover_dead_agents(conn)
                reclaim_timed_out_tasks(conn)

        except Exception as e:
            logging.error(f"Daemon error: {e}")

        await asyncio.sleep(10)  # Every 10 seconds
```

---

## CLI Interface

### Command Structure

```
aqua
├── init                    # Initialize Aqua in current directory
├── status                  # Show dashboard
├── add <title>             # Add a task
├── list                    # List tasks
├── join                    # Register as agent
├── leave                   # Deregister agent
├── claim [task_id]         # Claim a task
├── done [task_id]          # Mark task complete
├── fail [task_id]          # Mark task failed
├── progress <message>      # Update progress
├── msg <message>           # Send message
├── inbox                   # Read messages
├── watch                   # Live dashboard
├── log                     # View event log
├── doctor                  # Health check
└── daemon                  # Run background daemon
```

### Command Reference

#### `aqua init`

Initialize Aqua in the current directory.

```bash
aqua init [--force]

# Creates:
# .aqua/
# ├── aqua.db
# └── config.yaml (optional)
```

#### `aqua status`

Show the current state dashboard.

```bash
aqua status [--json]

# Output:
# Aqua Status - my-project
# ═══════════════════════════════════════
#
# Leader: claude-main (term 3, elected 5m ago)
#
# Agents (3 active):
#   NAME          TYPE     STATUS   TASK    HEARTBEAT
#   claude-main   claude   working  #a1b2   2s ago
#   codex-1       codex    idle     -       5s ago
#   gemini-1      gemini   working  #c3d4   3s ago
#
# Tasks:
#   PENDING: 3  │  CLAIMED: 2  │  DONE: 5  │  FAILED: 0
```

#### `aqua add`

Add a new task.

```bash
aqua add <title> [options]

Options:
  -d, --description TEXT  Detailed description
  -p, --priority INT      Priority 1-10 (default: 5)
  -t, --tag TEXT          Add tag (repeatable)
  --context TEXT          Additional context

Examples:
  aqua add "Implement login page"
  aqua add "Fix bug #123" -p 8 -t urgent -t backend
  aqua add "Write tests" -d "Unit tests for auth module"
```

#### `aqua list`

List tasks.

```bash
aqua list [options]

Options:
  -s, --status TEXT   Filter by status (pending, claimed, done, failed)
  -t, --tag TEXT      Filter by tag
  --json              Output as JSON

Examples:
  aqua list
  aqua list --status pending
  aqua list --tag urgent --json
```

#### `aqua join`

Register as an agent.

```bash
aqua join [options]

Options:
  -n, --name TEXT     Agent name (auto-generated if omitted)
  -t, --type TEXT     Agent type: claude, codex, gemini, generic
  -c, --cap TEXT      Capability (repeatable): code, test, docs, review

Examples:
  aqua join
  aqua join --name claude-main --type claude
  aqua join --name test-bot --cap test --cap docs
```

#### `aqua leave`

Leave the quorum gracefully.

```bash
aqua leave [--force]

# Releases any claimed tasks and deregisters the agent
```

#### `aqua claim`

Claim a task.

```bash
aqua claim [task_id] [--json]

# If task_id is omitted, claims highest priority available task
# Returns task details in JSON format with --json

Examples:
  aqua claim          # Claim next available
  aqua claim a1b2c3d4 # Claim specific task
```

#### `aqua done`

Mark a task as complete.

```bash
aqua done [task_id] [options]

Options:
  -s, --summary TEXT  Completion summary

# If task_id is omitted, completes the agent's current task

Examples:
  aqua done
  aqua done --summary "Implemented login with OAuth2"
  aqua done a1b2c3d4 -s "Fixed the bug"
```

#### `aqua fail`

Mark a task as failed.

```bash
aqua fail [task_id] --reason TEXT

Examples:
  aqua fail --reason "Blocked by missing API keys"
  aqua fail a1b2c3d4 --reason "Tests failing, needs investigation"
```

#### `aqua progress`

Report progress on current task.

```bash
aqua progress <message>

Examples:
  aqua progress "Working on database schema"
  aqua progress "50% complete, implementing API endpoints"
```

#### `aqua msg`

Send a message.

```bash
aqua msg <message> [options]

Options:
  --to TEXT   Recipient: agent-name, @all (broadcast), @leader, @idle

Examples:
  aqua msg "Hello everyone"              # Broadcast
  aqua msg "Need help" --to claude-main  # Direct message
  aqua msg "Task done" --to @leader      # To leader
```

#### `aqua inbox`

Read messages.

```bash
aqua inbox [options]

Options:
  --unread    Only show unread messages
  --from TEXT Filter by sender
  --json      Output as JSON
```

#### `aqua watch`

Live dashboard (requires daemon or frequent polling).

```bash
aqua watch [options]

Options:
  -r, --refresh INT   Refresh interval in seconds (default: 2)
```

#### `aqua doctor`

Health check.

```bash
aqua doctor

# Output:
# Aqua Health Check
# ─────────────────────
# [✓] Database accessible
# [✓] Schema up to date
# [✓] All agents have recent heartbeats
# [!] Task #a1b2 claimed for >30m (possible stuck)
# [✓] No orphaned tasks
#
# Overall: HEALTHY (1 warning)
```

### JSON Output Mode

All commands support `--json` flag for programmatic access:

```bash
aqua status --json | jq .leader.name
aqua list --json | jq '.[] | select(.status == "pending")'
aqua claim --json | jq .id
```

---

## Agent Integration Protocol

Aqua is designed to work with any CLI agent through a simple protocol.

### Protocol Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Agent Integration Protocol                 │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. REGISTRATION                                              │
│     Agent → aqua join --name X --type Y                       │
│     Aqua → Returns agent_id (store in env/file)               │
│                                                               │
│  2. HEARTBEAT                                                 │
│     - Implicit: Every aqua command updates heartbeat          │
│     - Explicit: Agent runs aqua daemon in background          │
│                                                               │
│  3. TASK LIFECYCLE                                            │
│     aqua claim → Get task (JSON)                              │
│     [Agent works on task]                                     │
│     aqua progress "status" → Report progress                  │
│     aqua done/fail → Complete task                            │
│                                                               │
│  4. COMMUNICATION                                             │
│     aqua msg "text" → Send message                            │
│     aqua inbox --json → Read messages                         │
│                                                               │
│  5. DEREGISTRATION                                            │
│     aqua leave → Clean exit                                   │
│     [Or timeout after 60s without heartbeat]                  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Integration Examples

#### Claude Code

Add to agent's context or `.claude/commands/`:

```markdown
## Aqua Coordination

You are part of a multi-agent team coordinated by Aqua.

### Commands
- Check status: `aqua status`
- Claim a task: `aqua claim` (returns JSON with task details)
- Report progress: `aqua progress "Working on X..."`
- Complete task: `aqua done --summary "What was accomplished"`
- Report failure: `aqua fail --reason "Why it failed"`
- Send message: `aqua msg "Hello" --to @all`
- Read messages: `aqua inbox --unread`

### Workflow
1. Run `aqua status` to see available tasks
2. Run `aqua claim` to get your next task
3. Work on the task
4. Run `aqua done --summary "..."` when complete
5. Check `aqua inbox --unread` for messages from other agents
```

#### Generic Script Integration

```python
#!/usr/bin/env python3
"""Example agent integration script."""

import subprocess
import json
import time
import sys

def aqua(args: list) -> dict:
    """Execute aqua command and parse JSON output."""
    result = subprocess.run(
        ['aqua'] + args + ['--json'],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout) if result.stdout else {}

def main():
    # Register
    agent = aqua(['join', '--name', f'worker-{os.getpid()}', '--type', 'generic'])
    if not agent:
        print("Failed to join")
        sys.exit(1)

    print(f"Joined as {agent['name']} (id: {agent['id']})")

    try:
        while True:
            # Claim task
            task = aqua(['claim'])
            if not task:
                print("No tasks available, waiting...")
                time.sleep(10)
                continue

            print(f"Claimed task: {task['title']}")

            # Simulate work
            aqua(['progress', 'Starting work...'])
            time.sleep(5)
            aqua(['progress', '50% complete'])
            time.sleep(5)

            # Complete
            aqua(['done', '--summary', f"Completed: {task['title']}"])
            print(f"Completed task {task['id']}")

    except KeyboardInterrupt:
        print("\nLeaving...")
        aqua(['leave'])

if __name__ == '__main__':
    main()
```

#### Environment Variable Integration

Agents can store their ID in environment variables:

```bash
# On join
export AQUA_AGENT_ID=$(aqua join --json | jq -r .id)
export AQUA_AGENT_NAME=$(aqua join --json | jq -r .name)

# Subsequent commands use these automatically
aqua claim
aqua done
```

---

## Failure Handling

### Failure Modes and Mitigations

| Failure Mode | Detection | Mitigation |
|--------------|-----------|------------|
| Agent crash | Heartbeat timeout + PID check | Mark dead, release tasks |
| Leader crash | Lease expiration | New leader elected |
| Task timeout | claimed_at older than threshold | Return to pending |
| Database corruption | PRAGMA integrity_check | Alert user, backup |
| Concurrent claim | UPDATE rowcount = 0 | Retry or return None |
| SQLite busy | SQLITE_BUSY error | Exponential backoff |

### SQLite Busy Handling

```python
import time
import random

MAX_RETRIES = 5
BASE_DELAY = 0.1  # 100ms

def execute_with_retry(conn, sql, params=None):
    """Execute SQL with exponential backoff on SQLITE_BUSY."""
    for attempt in range(MAX_RETRIES):
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or [])
            return cursor
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.1)
                time.sleep(delay)
                continue
            raise
```

### Graceful Degradation

```python
def safe_claim(agent_id: str, conn) -> Optional[Task]:
    """Claim with graceful degradation on failures."""
    try:
        return claim_task(agent_id, conn=conn)
    except sqlite3.OperationalError as e:
        logging.warning(f"Database busy, will retry: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error claiming task: {e}")
        return None
```

---

## Configuration

### Configuration File

Optional `.aqua/config.yaml`:

```yaml
# Aqua Configuration
# All values are optional - these are the defaults

# Timing parameters
timing:
  leader_lease_seconds: 30        # How long a leader lease lasts
  heartbeat_interval_seconds: 10  # How often to heartbeat (daemon mode)
  agent_dead_threshold_seconds: 60 # Consider dead after this silence
  task_claim_timeout_seconds: 600  # Reclaim stuck tasks after this

# Task behavior
tasks:
  default_priority: 5             # Default priority for new tasks
  max_retries: 3                  # Max times to retry failed tasks
  auto_recover_abandoned: true    # Automatically reclaim abandoned tasks

# Agent defaults
agents:
  default_type: generic           # Default agent type
  auto_name: true                 # Generate names if not provided

# Logging
logging:
  level: info                     # debug, info, warning, error
  file: null                      # Log to file (null = stderr only)

# Display
display:
  colors: true                    # Use colors in output
  unicode: true                   # Use unicode characters
```

### Environment Variables

Environment variables override config file:

```bash
AQUA_LEADER_LEASE_SECONDS=60
AQUA_HEARTBEAT_INTERVAL_SECONDS=15
AQUA_AGENT_DEAD_THRESHOLD_SECONDS=120
AQUA_LOG_LEVEL=debug
AQUA_NO_COLOR=1
```

### Configuration Loading

```python
from pathlib import Path
import yaml
import os

DEFAULT_CONFIG = {
    'timing': {
        'leader_lease_seconds': 30,
        'heartbeat_interval_seconds': 10,
        'agent_dead_threshold_seconds': 60,
        'task_claim_timeout_seconds': 600,
    },
    'tasks': {
        'default_priority': 5,
        'max_retries': 3,
        'auto_recover_abandoned': True,
    },
    # ... etc
}

def load_config(project_dir: Path) -> dict:
    """Load configuration with precedence: env > file > defaults."""
    config = DEFAULT_CONFIG.copy()

    # Load from file
    config_file = project_dir / '.aqua' / 'config.yaml'
    if config_file.exists():
        with open(config_file) as f:
            file_config = yaml.safe_load(f) or {}
            deep_merge(config, file_config)

    # Override from environment
    for key, value in os.environ.items():
        if key.startswith('AQUA_'):
            config_key = key[5:].lower()
            set_nested(config, config_key, parse_value(value))

    return config
```

---

## Security Considerations

### Threat Model

Aqua assumes a **trusted local environment**:
- All agents run on the same machine
- All agents have access to the same filesystem
- No authentication between agents
- No encryption of data at rest

### Security Properties

| Property | Status | Notes |
|----------|--------|-------|
| Authentication | Not implemented | Trust local processes |
| Authorization | Not implemented | All agents can do anything |
| Encryption at rest | Not implemented | SQLite is plaintext |
| Encryption in transit | N/A | All local IPC |
| Input validation | Implemented | SQL injection prevention |
| DoS protection | Partial | SQLite busy timeout |

### SQL Injection Prevention

All database operations use parameterized queries:

```python
# GOOD: Parameterized query
cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))

# BAD: String interpolation (NEVER DO THIS)
cursor.execute(f"SELECT * FROM tasks WHERE id = '{task_id}'")
```

### File Permissions

The `.aqua` directory should be readable only by the user:

```python
def init_aqua_dir(project_dir: Path):
    aqua_dir = project_dir / '.aqua'
    aqua_dir.mkdir(mode=0o700, exist_ok=True)  # rwx------
```

### Future Security Enhancements

If Aqua is extended for multi-machine use:
1. Add TLS for network communication
2. Add agent authentication (tokens or certificates)
3. Add role-based access control
4. Encrypt sensitive data at rest

---

## Future Extensions

### Planned Enhancements

#### 1. Task Dependencies

```yaml
# Allow tasks to depend on other tasks
tasks:
  - id: t1
    title: "Write code"
  - id: t2
    title: "Write tests"
    depends_on: [t1]
  - id: t3
    title: "Deploy"
    depends_on: [t1, t2]
```

#### 2. Agent Capabilities Matching

```python
# Match tasks to agents based on capabilities
@dataclass
class Task:
    required_capabilities: List[str]  # ["code", "python"]

def find_suitable_agent(task: Task, agents: List[Agent]) -> Optional[Agent]:
    for agent in agents:
        if set(task.required_capabilities) <= set(agent.capabilities):
            return agent
    return None
```

#### 3. Hooks System

```yaml
# .aqua/config.yaml
hooks:
  on_task_created:
    - ./hooks/notify-slack.sh
  on_task_completed:
    - ./hooks/update-jira.sh
  on_agent_died:
    - ./hooks/alert-pagerduty.sh
```

#### 4. Web Dashboard

```python
# Optional web UI for monitoring
@app.route('/api/status')
def api_status():
    return jsonify({
        'agents': get_all_agents(),
        'tasks': get_all_tasks(),
        'leader': get_current_leader()
    })
```

#### 5. Multi-Project Support

```bash
# Coordinate across multiple projects
aqua --project /path/to/project1 status
aqua --project /path/to/project2 status

# Or global coordination
aqua global status  # Shows all projects
```

### Extension Points

The design includes several extension points:

1. **Custom Agent Types**: Add new agent types in config
2. **Custom Task Statuses**: Extend status enum
3. **Plugin System**: Load Python plugins from `.aqua/plugins/`
4. **Custom Commands**: Add CLI commands via plugins

---

## Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| Agent | A CLI AI tool (Claude Code, Codex, etc.) participating in Aqua |
| Quorum | The set of all registered agents |
| Leader | The agent currently coordinating the quorum |
| Follower | Any agent that is not the leader |
| Term | A monotonically increasing number for each leader election |
| Lease | A time-limited lock on leadership |
| Fencing Token | A term number used to prevent stale operations |
| Heartbeat | Periodic signal that an agent is alive |

### B. Error Codes

| Code | Meaning |
|------|---------|
| AQUA_OK (0) | Success |
| AQUA_NOT_INITIALIZED (1) | No .aqua directory found |
| AQUA_NOT_JOINED (2) | Agent not registered |
| AQUA_NO_TASK (3) | No task to claim |
| AQUA_TASK_NOT_FOUND (4) | Task ID doesn't exist |
| AQUA_ALREADY_CLAIMED (5) | Task already claimed by another agent |
| AQUA_DB_ERROR (10) | Database error |
| AQUA_CONFIG_ERROR (11) | Configuration error |

### C. Database Migrations

For schema changes between versions:

```python
MIGRATIONS = [
    # v1 -> v2: Add task tags
    """ALTER TABLE tasks ADD COLUMN tags TEXT""",

    # v2 -> v3: Add message types
    """ALTER TABLE messages ADD COLUMN message_type TEXT DEFAULT 'chat'""",
]

def migrate_database(conn, from_version: int, to_version: int):
    for i in range(from_version, to_version):
        conn.execute(MIGRATIONS[i])
    conn.execute(f"PRAGMA user_version = {to_version}")
    conn.commit()
```

### D. Performance Characteristics

| Operation | Complexity | Typical Latency |
|-----------|------------|-----------------|
| claim_task | O(log n) | < 10ms |
| update_heartbeat | O(1) | < 5ms |
| try_become_leader | O(1) | < 10ms |
| recover_dead_agents | O(n) | < 100ms |
| list_tasks | O(n) | < 50ms |

Where n = number of tasks or agents.

### E. Testing Strategy

```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def temp_project():
    """Create a temporary project directory with Aqua initialized."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir)
        init_aqua(project)
        yield project

@pytest.fixture
def db(temp_project):
    """Get database connection for testing."""
    return get_db_connection(temp_project / '.aqua' / 'aqua.db')

# tests/test_leader.py
def test_first_agent_becomes_leader(db):
    """First agent to join should become leader."""
    agent_id = register_agent("test-1", db)
    is_leader, term = try_become_leader(agent_id, db)

    assert is_leader is True
    assert term == 1

def test_second_agent_becomes_follower(db):
    """Second agent should not become leader while first holds lease."""
    agent1 = register_agent("test-1", db)
    agent2 = register_agent("test-2", db)

    try_become_leader(agent1, db)  # Agent 1 becomes leader
    is_leader, term = try_become_leader(agent2, db)

    assert is_leader is False

def test_leader_takeover_after_lease_expires(db):
    """Agent should become leader after previous lease expires."""
    agent1 = register_agent("test-1", db)
    agent2 = register_agent("test-2", db)

    try_become_leader(agent1, db)

    # Simulate lease expiration
    expire_leader_lease(db)

    is_leader, term = try_become_leader(agent2, db)
    assert is_leader is True
    assert term == 2  # New term
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-25 | Vignesh | Initial design document |
