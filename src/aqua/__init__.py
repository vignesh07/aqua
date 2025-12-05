"""
Aqua - Autonomous QUorum of Agents

A lightweight, agent-agnostic coordinator for CLI AI agents.
"""

__version__ = "0.4.2"
__author__ = "Vignesh"

from aqua.models import Agent, AgentStatus, AgentType, Message, Task, TaskStatus

__all__ = [
    "__version__",
    "Agent",
    "Task",
    "Message",
    "AgentStatus",
    "AgentType",
    "TaskStatus",
]
