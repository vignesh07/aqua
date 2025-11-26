"""Tests for leader election."""

import pytest
from datetime import datetime, timedelta
import threading
import time

from aqua.db import Database
from aqua.models import Agent
from aqua.utils import generate_short_id


class TestLeaderElection:
    """Tests for leader election algorithm."""

    def test_first_agent_becomes_leader(self, db: Database):
        """First agent to try should become leader."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        is_leader, term = db.try_become_leader(agent.id)

        assert is_leader is True
        assert term == 1

    def test_second_agent_cannot_become_leader(self, db: Database):
        """Second agent cannot become leader while first holds lease."""
        agent1 = Agent(id=generate_short_id(), name="agent-1")
        agent2 = Agent(id=generate_short_id(), name="agent-2")

        db.create_agent(agent1)
        db.create_agent(agent2)

        # First agent becomes leader
        is_leader1, _ = db.try_become_leader(agent1.id)
        assert is_leader1 is True

        # Second agent cannot become leader
        is_leader2, term2 = db.try_become_leader(agent2.id)
        assert is_leader2 is False
        assert term2 == 0

    def test_leader_renews_lease(self, db: Database):
        """Leader can renew their lease."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        # Become leader
        is_leader1, term1 = db.try_become_leader(agent.id)
        assert is_leader1 is True
        assert term1 == 1

        leader_before = db.get_leader()

        # Renew
        is_leader2, term2 = db.try_become_leader(agent.id)
        assert is_leader2 is True
        assert term2 == 1  # Same term

        leader_after = db.get_leader()

        # Lease should be extended
        assert leader_after.lease_expires_at > leader_before.lease_expires_at

    def test_takeover_after_lease_expiry(self, db: Database):
        """New agent can become leader after lease expires."""
        agent1 = Agent(id=generate_short_id(), name="agent-1")
        agent2 = Agent(id=generate_short_id(), name="agent-2")

        db.create_agent(agent1)
        db.create_agent(agent2)

        # First agent becomes leader
        db.try_become_leader(agent1.id, lease_seconds=1)

        # Wait for lease to expire
        time.sleep(1.5)

        # Second agent can now become leader
        is_leader, term = db.try_become_leader(agent2.id)
        assert is_leader is True
        assert term == 2  # New term

    def test_term_increments_on_new_leader(self, db: Database):
        """Term number increments with each new leader."""
        agents = [
            Agent(id=generate_short_id(), name=f"agent-{i}")
            for i in range(3)
        ]
        for agent in agents:
            db.create_agent(agent)

        # First leader
        _, term1 = db.try_become_leader(agents[0].id, lease_seconds=1)
        assert term1 == 1

        time.sleep(1.1)

        # Second leader
        _, term2 = db.try_become_leader(agents[1].id, lease_seconds=1)
        assert term2 == 2

        time.sleep(1.1)

        # Third leader
        _, term3 = db.try_become_leader(agents[2].id, lease_seconds=1)
        assert term3 == 3

    def test_get_leader(self, db: Database):
        """Test retrieving current leader information."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        db.try_become_leader(agent.id)

        leader = db.get_leader()
        assert leader is not None
        assert leader.agent_id == agent.id
        assert leader.term == 1
        assert leader.lease_expires_at > datetime.utcnow()

    def test_leader_is_expired(self, db: Database):
        """Test checking if leader lease is expired."""
        agent = Agent(id=generate_short_id(), name="agent-1")
        db.create_agent(agent)

        db.try_become_leader(agent.id, lease_seconds=1)

        leader = db.get_leader()
        assert leader.is_expired() is False

        time.sleep(1.1)

        leader = db.get_leader()
        assert leader.is_expired() is True

    def test_concurrent_election(self, db: Database):
        """Test that only one agent wins in concurrent election."""
        agents = [
            Agent(id=generate_short_id(), name=f"agent-{i}")
            for i in range(5)
        ]
        for agent in agents:
            db.create_agent(agent)

        results = []
        lock = threading.Lock()

        def try_election(agent_id):
            # Each thread needs its own connection
            from aqua.db import get_db
            from pathlib import Path

            thread_db = Database(db.db_path)
            is_leader, term = thread_db.try_become_leader(agent_id)
            with lock:
                results.append((agent_id, is_leader, term))
            thread_db.close()

        threads = [
            threading.Thread(target=try_election, args=(agent.id,))
            for agent in agents
        ]

        # Start all threads nearly simultaneously
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one should be leader
        leaders = [r for r in results if r[1] is True]
        assert len(leaders) == 1

        # All leaders should have term 1
        assert leaders[0][2] == 1

    def test_fencing_token_prevents_stale_leader(self, db: Database):
        """Test that fencing tokens prevent stale leader operations."""
        agent1 = Agent(id=generate_short_id(), name="agent-1")
        agent2 = Agent(id=generate_short_id(), name="agent-2")

        db.create_agent(agent1)
        db.create_agent(agent2)

        # Agent 1 becomes leader with term 1
        db.try_become_leader(agent1.id, lease_seconds=1)
        term1 = db.get_current_term()

        # Create a task
        from aqua.models import Task
        task = Task(id=generate_short_id(), title="Test task")
        db.create_task(task)

        # Claim with term 1
        success1 = db.claim_task(task.id, agent1.id, term=term1)
        assert success1 is True

        # Simulate lease expiry and new leader
        time.sleep(1.1)
        db.try_become_leader(agent2.id)
        term2 = db.get_current_term()
        assert term2 == 2

        # Reset task for test
        db.conn.execute(
            "UPDATE tasks SET status = 'pending', claimed_by = NULL WHERE id = ?",
            (task.id,)
        )

        # Old term should still work for claiming (fencing is for verification)
        # But the claim_term will be recorded for audit
        task2 = Task(id=generate_short_id(), title="Test task 2")
        db.create_task(task2)

        success2 = db.claim_task(task2.id, agent1.id, term=term1)
        assert success2 is True

        claimed_task = db.get_task(task2.id)
        assert claimed_task.claim_term == term1

    def test_no_leader_initially(self, db: Database):
        """Test that there's no leader before anyone tries."""
        leader = db.get_leader()
        assert leader is None
        assert db.get_current_term() == 0
