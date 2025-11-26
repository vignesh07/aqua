"""Tests for database operations."""

import pytest
from datetime import datetime, timedelta

from aqua.db import Database
from aqua.models import Agent, Task, AgentStatus, AgentType, TaskStatus
from aqua.utils import generate_short_id


class TestAgentOperations:
    """Tests for agent CRUD operations."""

    def test_create_agent(self, db: Database, sample_agent: Agent):
        """Test creating an agent."""
        created = db.create_agent(sample_agent)
        assert created.id == sample_agent.id
        assert created.name == sample_agent.name

    def test_get_agent(self, db: Database, sample_agent: Agent):
        """Test retrieving an agent."""
        db.create_agent(sample_agent)
        retrieved = db.get_agent(sample_agent.id)

        assert retrieved is not None
        assert retrieved.id == sample_agent.id
        assert retrieved.name == sample_agent.name

    def test_get_agent_not_found(self, db: Database):
        """Test retrieving non-existent agent."""
        retrieved = db.get_agent("nonexistent")
        assert retrieved is None

    def test_get_agent_by_name(self, db: Database, sample_agent: Agent):
        """Test retrieving agent by name."""
        db.create_agent(sample_agent)
        retrieved = db.get_agent_by_name(sample_agent.name)

        assert retrieved is not None
        assert retrieved.id == sample_agent.id

    def test_get_all_agents(self, db_with_agents: Database):
        """Test retrieving all agents."""
        agents = db_with_agents.get_all_agents()
        assert len(agents) == 3

    def test_get_all_agents_filtered(self, db_with_agents: Database):
        """Test filtering agents by status."""
        active_agents = db_with_agents.get_all_agents(status=AgentStatus.ACTIVE)
        assert len(active_agents) == 3

        dead_agents = db_with_agents.get_all_agents(status=AgentStatus.DEAD)
        assert len(dead_agents) == 0

    def test_update_heartbeat(self, db: Database, sample_agent: Agent):
        """Test updating agent heartbeat."""
        db.create_agent(sample_agent)
        original = db.get_agent(sample_agent.id)

        # Wait a tiny bit and update
        db.update_heartbeat(sample_agent.id)
        updated = db.get_agent(sample_agent.id)

        assert updated.last_heartbeat_at >= original.last_heartbeat_at

    def test_update_agent_status(self, db: Database, sample_agent: Agent):
        """Test updating agent status."""
        db.create_agent(sample_agent)

        db.update_agent_status(sample_agent.id, AgentStatus.DEAD)
        updated = db.get_agent(sample_agent.id)

        assert updated.status == AgentStatus.DEAD

    def test_delete_agent(self, db: Database, sample_agent: Agent):
        """Test deleting an agent."""
        db.create_agent(sample_agent)
        db.delete_agent(sample_agent.id)

        retrieved = db.get_agent(sample_agent.id)
        assert retrieved is None


class TestTaskOperations:
    """Tests for task CRUD operations."""

    def test_create_task(self, db: Database, sample_task: Task):
        """Test creating a task."""
        created = db.create_task(sample_task)
        assert created.id == sample_task.id
        assert created.title == sample_task.title

    def test_get_task(self, db: Database, sample_task: Task):
        """Test retrieving a task."""
        db.create_task(sample_task)
        retrieved = db.get_task(sample_task.id)

        assert retrieved is not None
        assert retrieved.title == sample_task.title

    def test_get_all_tasks(self, db_with_tasks: Database):
        """Test retrieving all tasks."""
        tasks = db_with_tasks.get_all_tasks()
        assert len(tasks) == 3

    def test_get_all_tasks_filtered_by_status(self, db_with_tasks: Database):
        """Test filtering tasks by status."""
        pending = db_with_tasks.get_all_tasks(status=TaskStatus.PENDING)
        assert len(pending) == 3

        done = db_with_tasks.get_all_tasks(status=TaskStatus.DONE)
        assert len(done) == 0

    def test_get_next_pending_task_priority(self, db_with_tasks: Database):
        """Test getting next task respects priority."""
        task = db_with_tasks.get_next_pending_task()
        assert task is not None
        assert task.priority == 10  # Highest priority

    def test_claim_task(self, db: Database, sample_agent: Agent, sample_task: Task):
        """Test claiming a task."""
        db.create_agent(sample_agent)
        db.create_task(sample_task)

        success = db.claim_task(sample_task.id, sample_agent.id, term=1)
        assert success is True

        task = db.get_task(sample_task.id)
        assert task.status == TaskStatus.CLAIMED
        assert task.claimed_by == sample_agent.id

    def test_claim_task_already_claimed(self, db: Database, sample_task: Task):
        """Test that already claimed task cannot be claimed again."""
        agent1 = Agent(id=generate_short_id(), name="agent-1")
        agent2 = Agent(id=generate_short_id(), name="agent-2")

        db.create_agent(agent1)
        db.create_agent(agent2)
        db.create_task(sample_task)

        # First claim succeeds
        success1 = db.claim_task(sample_task.id, agent1.id, term=1)
        assert success1 is True

        # Second claim fails
        success2 = db.claim_task(sample_task.id, agent2.id, term=1)
        assert success2 is False

    def test_complete_task(self, db: Database, sample_agent: Agent, sample_task: Task):
        """Test completing a task."""
        db.create_agent(sample_agent)
        db.create_task(sample_task)
        db.claim_task(sample_task.id, sample_agent.id, term=1)

        success = db.complete_task(sample_task.id, sample_agent.id, result="Done!")
        assert success is True

        task = db.get_task(sample_task.id)
        assert task.status == TaskStatus.DONE
        assert task.result == "Done!"

    def test_fail_task(self, db: Database, sample_agent: Agent, sample_task: Task):
        """Test failing a task."""
        db.create_agent(sample_agent)
        db.create_task(sample_task)
        db.claim_task(sample_task.id, sample_agent.id, term=1)

        success = db.fail_task(sample_task.id, sample_agent.id, error="Something went wrong")
        assert success is True

        task = db.get_task(sample_task.id)
        assert task.status == TaskStatus.FAILED
        assert task.error == "Something went wrong"

    def test_abandon_task(self, db: Database, sample_agent: Agent, sample_task: Task):
        """Test abandoning a task."""
        db.create_agent(sample_agent)
        db.create_task(sample_task)
        db.claim_task(sample_task.id, sample_agent.id, term=1)

        success = db.abandon_task(sample_task.id, reason="Agent died")
        assert success is True

        task = db.get_task(sample_task.id)
        assert task.status == TaskStatus.ABANDONED
        assert task.claimed_by is None

    def test_get_task_counts(self, db_with_tasks: Database):
        """Test getting task counts."""
        counts = db_with_tasks.get_task_counts()

        assert counts["pending"] == 3
        assert counts["claimed"] == 0
        assert counts["done"] == 0


class TestLeaderOperations:
    """Tests for leader election operations."""

    def test_first_agent_becomes_leader(self, db: Database, sample_agent: Agent):
        """Test first agent becomes leader."""
        db.create_agent(sample_agent)

        is_leader, term = db.try_become_leader(sample_agent.id)

        assert is_leader is True
        assert term == 1

    def test_second_agent_not_leader(self, db: Database):
        """Test second agent doesn't become leader while first holds lease."""
        agent1 = Agent(id=generate_short_id(), name="agent-1")
        agent2 = Agent(id=generate_short_id(), name="agent-2")

        db.create_agent(agent1)
        db.create_agent(agent2)

        # First agent becomes leader
        is_leader1, term1 = db.try_become_leader(agent1.id)
        assert is_leader1 is True

        # Second agent cannot become leader
        is_leader2, term2 = db.try_become_leader(agent2.id)
        assert is_leader2 is False
        assert term2 == 0

    def test_leader_renews_lease(self, db: Database, sample_agent: Agent):
        """Test leader can renew their lease."""
        db.create_agent(sample_agent)

        # Become leader
        is_leader1, term1 = db.try_become_leader(sample_agent.id)
        assert is_leader1 is True

        # Renew lease (should succeed with same term)
        is_leader2, term2 = db.try_become_leader(sample_agent.id)
        assert is_leader2 is True
        assert term2 == term1

    def test_get_leader(self, db: Database, sample_agent: Agent):
        """Test getting current leader."""
        db.create_agent(sample_agent)
        db.try_become_leader(sample_agent.id)

        leader = db.get_leader()
        assert leader is not None
        assert leader.agent_id == sample_agent.id
        assert leader.term == 1

    def test_get_current_term(self, db: Database, sample_agent: Agent):
        """Test getting current term."""
        # No leader yet
        assert db.get_current_term() == 0

        db.create_agent(sample_agent)
        db.try_become_leader(sample_agent.id)

        assert db.get_current_term() == 1


class TestMessageOperations:
    """Tests for message operations."""

    def test_create_message(self, db: Database, sample_agent: Agent):
        """Test creating a message."""
        db.create_agent(sample_agent)

        msg = db.create_message(sample_agent.id, "Hello, world!")

        assert msg.from_agent == sample_agent.id
        assert msg.content == "Hello, world!"
        assert msg.to_agent is None  # Broadcast

    def test_create_direct_message(self, db: Database):
        """Test creating a direct message."""
        agent1 = Agent(id=generate_short_id(), name="agent-1")
        agent2 = Agent(id=generate_short_id(), name="agent-2")

        db.create_agent(agent1)
        db.create_agent(agent2)

        msg = db.create_message(agent1.id, "Hello agent 2!", to_agent=agent2.id)

        assert msg.from_agent == agent1.id
        assert msg.to_agent == agent2.id

    def test_get_messages(self, db: Database, sample_agent: Agent):
        """Test getting messages."""
        db.create_agent(sample_agent)

        db.create_message(sample_agent.id, "Message 1")
        db.create_message(sample_agent.id, "Message 2")

        messages = db.get_messages()
        assert len(messages) == 2

    def test_get_unread_messages(self, db: Database, sample_agent: Agent):
        """Test getting only unread messages."""
        db.create_agent(sample_agent)

        msg1 = db.create_message(sample_agent.id, "Message 1")
        msg2 = db.create_message(sample_agent.id, "Message 2")

        # Mark one as read
        db.mark_messages_read(sample_agent.id, [msg1.id])

        unread = db.get_messages(unread_only=True)
        assert len(unread) == 1
        assert unread[0].id == msg2.id


class TestEventLog:
    """Tests for event logging."""

    def test_log_event(self, db: Database, sample_agent: Agent):
        """Test logging an event."""
        db.create_agent(sample_agent)

        db.log_event(
            "test_event",
            agent_id=sample_agent.id,
            details={"key": "value"}
        )

        events = db.get_events(event_type="test_event")
        assert len(events) == 1
        assert events[0].agent_id == sample_agent.id
        assert events[0].details["key"] == "value"

    def test_get_events_filtered(self, db: Database, sample_agent: Agent):
        """Test filtering events."""
        db.create_agent(sample_agent)

        db.log_event("event_a", agent_id=sample_agent.id)
        db.log_event("event_b", agent_id=sample_agent.id)
        db.log_event("event_a", agent_id=sample_agent.id)

        events_a = db.get_events(event_type="event_a")
        assert len(events_a) == 2

        events_b = db.get_events(event_type="event_b")
        assert len(events_b) == 1
