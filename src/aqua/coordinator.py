"""Coordinator logic for task management and crash recovery."""

from datetime import timedelta

from aqua.db import Database
from aqua.models import Agent, AgentStatus, Task, TaskStatus
from aqua.utils import process_exists, utc_now


def _utc_now_naive():
    """Get current UTC time as naive datetime for comparisons with DB values."""
    return utc_now().replace(tzinfo=None)

# Configuration defaults
# 5 minutes - LLM operations can take several minutes
AGENT_DEAD_THRESHOLD_SECONDS = 300
TASK_CLAIM_TIMEOUT_SECONDS = 1800  # 30 minutes for complex tasks


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

    def claim_next_task(self, agent_id: str) -> Task | None:
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

    def claim_next_task_for_role(self, agent_id: str) -> tuple[Task | None, bool]:
        """
        Claim the next available task, preferring tasks matching agent's role.

        Returns:
            Tuple of (task, is_role_match):
            - task: The claimed task, or None if no tasks available
            - is_role_match: True if task matches agent's role (or agent has no role)
        """
        # Get agent to check their role
        agent = self.db.get_agent(agent_id)
        role = agent.role if agent else None

        # Get current term for fencing
        term = self.db.get_current_term()

        # Find next pending task (with role preference if applicable)
        task, is_match = self.db.get_next_pending_task_for_role(role)
        if not task:
            return (None, True)  # No tasks = no mismatch

        # Attempt atomic claim
        if self.db.claim_task(task.id, agent_id, term):
            # Update agent's current task
            self.db.update_agent_task(agent_id, task.id)
            # Refresh task data
            return (self.db.get_task(task.id), is_match)

        return (None, True)  # Claim failed = no mismatch to report

    def claim_specific_task(self, agent_id: str, task_id: str) -> Task | None:
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
        self, agent_id: str, task_id: str | None = None, result: str | None = None
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
        self, agent_id: str, task_id: str | None = None, error: str = "Task failed"
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

    def recover_dead_agents(self) -> list[str]:
        """
        Detect crashed agents and release their tasks.
        Returns list of recovered agent IDs.
        """
        now = _utc_now_naive()
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
        now = _utc_now_naive()
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
