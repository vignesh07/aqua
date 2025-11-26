"""Coordinator logic for task management and crash recovery."""

from datetime import datetime, timedelta
from typing import Optional, List

from aqua.db import Database
from aqua.models import Agent, Task, AgentStatus, TaskStatus
from aqua.utils import process_exists


# Configuration defaults
AGENT_DEAD_THRESHOLD_SECONDS = 60
TASK_CLAIM_TIMEOUT_SECONDS = 600  # 10 minutes


class Coordinator:
    """Handles task coordination and crash recovery."""

    def __init__(
        self,
        db: Database,
        dead_threshold: int = AGENT_DEAD_THRESHOLD_SECONDS,
        claim_timeout: int = TASK_CLAIM_TIMEOUT_SECONDS,
    ):
        self.db = db
        self.dead_threshold = timedelta(seconds=dead_threshold)
        self.claim_timeout = timedelta(seconds=claim_timeout)

    def claim_next_task(self, agent_id: str) -> Optional[Task]:
        """
        Claim the next available task for an agent.
        Returns the claimed task or None if no tasks available.
        """
        # Get current term for fencing
        term = self.db.get_current_term()

        # Find next pending task
        task = self.db.get_next_pending_task()
        if not task:
            return None

        # Attempt atomic claim
        if self.db.claim_task(task.id, agent_id, term):
            # Update agent's current task
            self.db.update_agent_task(agent_id, task.id)
            # Refresh task data
            return self.db.get_task(task.id)

        return None

    def claim_specific_task(self, agent_id: str, task_id: str) -> Optional[Task]:
        """
        Claim a specific task for an agent.
        Returns the claimed task or None if claim failed.
        """
        term = self.db.get_current_term()

        if self.db.claim_task(task_id, agent_id, term):
            self.db.update_agent_task(agent_id, task_id)
            return self.db.get_task(task_id)

        return None

    def complete_task(
        self, agent_id: str, task_id: Optional[str] = None, result: Optional[str] = None
    ) -> bool:
        """
        Complete a task.
        If task_id is None, completes the agent's current task.
        """
        if task_id is None:
            agent = self.db.get_agent(agent_id)
            if not agent or not agent.current_task_id:
                return False
            task_id = agent.current_task_id

        if self.db.complete_task(task_id, agent_id, result):
            self.db.update_agent_task(agent_id, None)
            return True
        return False

    def fail_task(
        self, agent_id: str, task_id: Optional[str] = None, error: str = "Task failed"
    ) -> bool:
        """
        Mark a task as failed.
        If task_id is None, fails the agent's current task.
        """
        if task_id is None:
            agent = self.db.get_agent(agent_id)
            if not agent or not agent.current_task_id:
                return False
            task_id = agent.current_task_id

        if self.db.fail_task(task_id, agent_id, error):
            self.db.update_agent_task(agent_id, None)
            return True
        return False

    def recover_dead_agents(self) -> List[str]:
        """
        Detect crashed agents and release their tasks.
        Returns list of recovered agent IDs.
        """
        now = datetime.utcnow()
        threshold = now - self.dead_threshold
        recovered = []

        # Get all active agents
        agents = self.db.get_all_agents(status=AgentStatus.ACTIVE)

        for agent in agents:
            # Check if heartbeat is stale
            if agent.last_heartbeat_at >= threshold:
                continue

            # Double-check: is process actually dead?
            if agent.pid and process_exists(agent.pid):
                # Process alive but not heartbeating - log warning but don't kill
                self.db.log_event(
                    "agent_unresponsive",
                    agent_id=agent.id,
                    details={
                        "pid": agent.pid,
                        "last_heartbeat": agent.last_heartbeat_at.isoformat(),
                    }
                )
                continue

            # Agent is dead - recover
            self._recover_agent(agent)
            recovered.append(agent.id)

        return recovered

    def _recover_agent(self, agent: Agent) -> None:
        """Recover a dead agent's tasks."""
        # Mark agent as dead
        self.db.update_agent_status(agent.id, AgentStatus.DEAD)

        # Find and abandon their tasks
        tasks = self.db.get_all_tasks(status=TaskStatus.CLAIMED, claimed_by=agent.id)
        for task in tasks:
            self.db.abandon_task(task.id, reason=f"Agent {agent.name} died")

        self.db.log_event(
            "agent_died",
            agent_id=agent.id,
            details={
                "reason": "heartbeat_timeout",
                "pid": agent.pid,
                "tasks_released": len(tasks),
            }
        )

    def recover_stale_tasks(self) -> int:
        """
        Recover tasks that have been claimed too long without completion.
        Returns count of recovered tasks.
        """
        now = datetime.utcnow()
        threshold = now - self.claim_timeout

        # Find stale claimed tasks
        tasks = self.db.get_all_tasks(status=TaskStatus.CLAIMED)
        recovered = 0

        for task in tasks:
            if task.claimed_at and task.claimed_at < threshold:
                self.db.abandon_task(
                    task.id,
                    reason=f"Task timed out after {self.claim_timeout.total_seconds()}s"
                )
                recovered += 1

        return recovered

    def run_recovery(self) -> dict:
        """
        Run full recovery cycle.
        Returns summary of recovery actions.
        """
        dead_agents = self.recover_dead_agents()
        stale_tasks = self.recover_stale_tasks()
        requeued = self.db.requeue_abandoned_tasks()

        return {
            "dead_agents": dead_agents,
            "stale_tasks": stale_tasks,
            "requeued_tasks": requeued,
        }


def get_coordinator(db: Database) -> Coordinator:
    """Get a coordinator instance."""
    return Coordinator(db)
