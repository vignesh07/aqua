"""Pytest fixtures for Aqua tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from aqua.db import Database, init_db
from aqua.models import Agent, Task, AgentType, TaskStatus
from aqua.utils import generate_short_id


@pytest.fixture
def temp_project() -> Generator[Path, None, None]:
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def db(temp_project: Path) -> Generator[Database, None, None]:
    """Create a database in the temp project."""
    database = init_db(temp_project)
    yield database
    database.close()


@pytest.fixture
def sample_agent() -> Agent:
    """Create a sample agent."""
    return Agent(
        id=generate_short_id(),
        name="test-agent",
        agent_type=AgentType.GENERIC,
        pid=os.getpid(),
    )


@pytest.fixture
def sample_task() -> Task:
    """Create a sample task."""
    return Task(
        id=generate_short_id(),
        title="Test task",
        description="A test task for unit tests",
        priority=5,
    )


@pytest.fixture
def db_with_agents(db: Database) -> Database:
    """Create a database with some agents."""
    agents = [
        Agent(id=generate_short_id(), name="agent-1", agent_type=AgentType.CLAUDE, pid=1001),
        Agent(id=generate_short_id(), name="agent-2", agent_type=AgentType.CODEX, pid=1002),
        Agent(id=generate_short_id(), name="agent-3", agent_type=AgentType.GENERIC, pid=1003),
    ]
    for agent in agents:
        db.create_agent(agent)
    return db


@pytest.fixture
def db_with_tasks(db: Database) -> Database:
    """Create a database with some tasks."""
    tasks = [
        Task(id=generate_short_id(), title="High priority task", priority=10),
        Task(id=generate_short_id(), title="Medium priority task", priority=5),
        Task(id=generate_short_id(), title="Low priority task", priority=1),
    ]
    for task in tasks:
        db.create_task(task)
    return db
