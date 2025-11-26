"""Tests for coordinator and crash recovery."""

import pytest
from datetime import datetime, timedelta

from aqua.db import Database
from aqua.coordinator import Coordinator
from aqua.models import Agent, Task, AgentStatus, TaskStatus
from aqua.utils import generate_short_id


class TestTaskClaiming:
    """Tests for task claiming logic."""

    def test_claim_next_task(self, db: Database):
        """Test claiming next available task."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task", priority=5)
        db.create_task(task)

        coordinator = Coordinator(db)
        claimed = coordinator.claim_next_task(agent.id)

        assert claimed is not None
        assert claimed.id == task.id
        assert claimed.status == TaskStatus.CLAIMED
        assert claimed.claimed_by == agent.id

    def test_claim_respects_priority(self, db: Database):
        """Test that higher priority tasks are claimed first."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        low_priority = Task(id=generate_short_id(), title="Low priority", priority=1)
        high_priority = Task(id=generate_short_id(), title="High priority", priority=10)

        db.create_task(low_priority)
        db.create_task(high_priority)

        coordinator = Coordinator(db)
        claimed = coordinator.claim_next_task(agent.id)

        assert claimed.title == "High priority"

    def test_claim_specific_task(self, db: Database):
        """Test claiming a specific task by ID."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task1 = Task(id=generate_short_id(), title="Task 1")
        task2 = Task(id=generate_short_id(), title="Task 2")

        db.create_task(task1)
        db.create_task(task2)

        coordinator = Coordinator(db)
        claimed = coordinator.claim_specific_task(agent.id, task2.id)

        assert claimed.id == task2.id

    def test_claim_no_tasks_available(self, db: Database):
        """Test claiming when no tasks are available."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        coordinator = Coordinator(db)
        claimed = coordinator.claim_next_task(agent.id)

        assert claimed is None

    def test_claim_updates_agent_current_task(self, db: Database):
        """Test that claiming updates the agent's current task."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        coordinator = Coordinator(db)
        coordinator.claim_next_task(agent.id)

        updated_agent = db.get_agent(agent.id)
        assert updated_agent.current_task_id == task.id


class TestTaskCompletion:
    """Tests for task completion logic."""

    def test_complete_task(self, db: Database):
        """Test completing a task."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        coordinator = Coordinator(db)
        coordinator.claim_next_task(agent.id)

        success = coordinator.complete_task(agent.id, task.id, result="Finished!")
        assert success is True

        completed_task = db.get_task(task.id)
        assert completed_task.status == TaskStatus.DONE
        assert completed_task.result == "Finished!"

    def test_complete_current_task(self, db: Database):
        """Test completing current task without specifying ID."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        coordinator = Coordinator(db)
        coordinator.claim_next_task(agent.id)

        # Complete without specifying task_id
        success = coordinator.complete_task(agent.id, result="Done!")
        assert success is True

    def test_complete_clears_agent_current_task(self, db: Database):
        """Test that completing clears the agent's current task."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        coordinator = Coordinator(db)
        coordinator.claim_next_task(agent.id)
        coordinator.complete_task(agent.id, task.id)

        updated_agent = db.get_agent(agent.id)
        assert updated_agent.current_task_id is None


class TestTaskFailure:
    """Tests for task failure logic."""

    def test_fail_task(self, db: Database):
        """Test failing a task."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        coordinator = Coordinator(db)
        coordinator.claim_next_task(agent.id)

        success = coordinator.fail_task(agent.id, task.id, error="Something broke")
        assert success is True

        failed_task = db.get_task(task.id)
        assert failed_task.status == TaskStatus.FAILED
        assert failed_task.error == "Something broke"

    def test_fail_increments_retry_count(self, db: Database):
        """Test that failing increments retry count."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        coordinator = Coordinator(db)
        coordinator.claim_next_task(agent.id)
        coordinator.fail_task(agent.id, task.id, error="Error")

        failed_task = db.get_task(task.id)
        assert failed_task.retry_count == 1


class TestCrashRecovery:
    """Tests for crash detection and recovery."""

    def test_recover_dead_agent(self, db: Database):
        """Test recovering tasks from a dead agent."""
        agent = Agent(id=generate_short_id(), name="agent-1", pid=99999)  # Non-existent PID
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)
        db.claim_task(task.id, agent.id, term=1)

        # Simulate stale heartbeat
        stale_time = (datetime.utcnow() - timedelta(seconds=120)).isoformat()
        db.conn.execute(
            "UPDATE agents SET last_heartbeat_at = ? WHERE id = ?",
            (stale_time, agent.id)
        )

        coordinator = Coordinator(db, dead_threshold=60)
        recovered = coordinator.recover_dead_agents()

        assert agent.id in recovered

        # Check agent marked as dead
        dead_agent = db.get_agent(agent.id)
        assert dead_agent.status == AgentStatus.DEAD

        # Check task abandoned
        abandoned_task = db.get_task(task.id)
        assert abandoned_task.status == TaskStatus.ABANDONED

    def test_no_false_positive_recovery(self, db: Database):
        """Test that active agents are not marked dead."""
        agent = Agent(id=generate_short_id(), name="agent-1", pid=99999)
        db.create_agent(agent)

        # Fresh heartbeat
        db.update_heartbeat(agent.id)

        coordinator = Coordinator(db, dead_threshold=60)
        recovered = coordinator.recover_dead_agents()

        assert len(recovered) == 0
        assert db.get_agent(agent.id).status == AgentStatus.ACTIVE

    def test_recover_stale_tasks(self, db: Database):
        """Test recovering tasks that have been claimed too long."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)
        db.claim_task(task.id, agent.id, term=1)

        # Simulate old claim time
        old_time = (datetime.utcnow() - timedelta(minutes=60)).isoformat()
        db.conn.execute(
            "UPDATE tasks SET claimed_at = ? WHERE id = ?",
            (old_time, task.id)
        )

        coordinator = Coordinator(db, claim_timeout=600)  # 10 minute timeout
        recovered_count = coordinator.recover_stale_tasks()

        assert recovered_count == 1

        stale_task = db.get_task(task.id)
        assert stale_task.status == TaskStatus.ABANDONED

    def test_requeue_abandoned_tasks(self, db: Database):
        """Test requeuing abandoned tasks under retry limit."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task", max_retries=3)
        db.create_task(task)
        db.claim_task(task.id, agent.id, term=1)
        db.abandon_task(task.id, reason="Test")

        requeued = db.requeue_abandoned_tasks()
        assert requeued == 1

        requeued_task = db.get_task(task.id)
        assert requeued_task.status == TaskStatus.PENDING

    def test_no_requeue_over_retry_limit(self, db: Database):
        """Test that tasks over retry limit are not requeued."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        task = Task(id=generate_short_id(), title="Test task", max_retries=1)
        db.create_task(task)
        db.claim_task(task.id, agent.id, term=1)

        # Fail multiple times
        db.conn.execute(
            "UPDATE tasks SET status = 'abandoned', retry_count = 5 WHERE id = ?",
            (task.id,)
        )

        requeued = db.requeue_abandoned_tasks()
        assert requeued == 0

    def test_run_recovery(self, db: Database):
        """Test running full recovery cycle."""
        coordinator = Coordinator(db)
        result = coordinator.run_recovery()

        assert "dead_agents" in result
        assert "stale_tasks" in result
        assert "requeued_tasks" in result
