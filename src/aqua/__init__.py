"""
Aqua - Autonomous QUorum of Agents

A lightweight, agent-agnostic coordinator for CLI AI agents.
"""

__version__ = "0.1.0"
__author__ = "Vignesh"

from aqua.models import Agent, Task, Message, AgentStatus, AgentType, TaskStatus

__all__ = [
    "__version__",
    "Agent",
    "Task",
    "Message",
    "AgentStatus",
    "AgentType",
    "TaskStatus",
]
