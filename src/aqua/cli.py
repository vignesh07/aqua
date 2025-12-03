"""Command-line interface for Aqua."""

import functools
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from aqua import __version__
from aqua.db import Database, init_db, get_db
from aqua.models import Agent, Task, AgentStatus, AgentType, TaskStatus
from aqua.coordinator import Coordinator
from aqua.utils import (
    generate_short_id,
    generate_agent_name,
    get_current_pid,
    format_time_ago,
    truncate,
    parse_tags,
    process_exists,
)

console = Console()

# Environment variable for storing agent ID (persists across commands in same shell)
AQUA_AGENT_ID_VAR = "AQUA_AGENT_ID"


def get_project_dir() -> Path:
    """Get the project directory (containing .aqua)."""
    # Search upward for .aqua directory
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / ".aqua").exists():
            return parent
    return cwd


def find_aqua_dir() -> Optional[Path]:
    """Find the .aqua directory."""
    project = get_project_dir()
    aqua_dir = project / ".aqua"
    return aqua_dir if aqua_dir.exists() else None


def require_init(func):
    """Decorator that requires Aqua to be initialized."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not find_aqua_dir():
            console.print("[red]Error:[/red] Aqua not initialized. Run 'aqua init' first.")
            sys.exit(1)
        return func(*args, **kwargs)
    return wrapper


def _get_session_id() -> str:
    """Get a unique session identifier for this terminal/agent.

    Uses multiple signals to identify a unique session:
    1. AQUA_SESSION_ID env var (explicit override)
    2. AQUA_AGENT_ID env var (agent already knows its ID)
    3. Terminal TTY device (unique per terminal window)
    4. Default "default" (single-agent mode for AI agents)

    Note: We avoid PPID because each subprocess has a different parent.
    For AI agents running commands, we use a simple "default" session
    which means one agent per directory. Use AQUA_SESSION_ID or
    AQUA_AGENT_ID for multi-agent in same directory.
    """
    # Check if we have an explicit session ID
    session_id = os.environ.get("AQUA_SESSION_ID")
    if session_id:
        return session_id

    # If agent ID is in env, use that as session (agent already identified)
    agent_id = os.environ.get(AQUA_AGENT_ID_VAR)
    if agent_id:
        return f"agent_{agent_id}"

    # Try to get TTY - unique per terminal window
    try:
        tty = os.ttyname(0)
        return tty.replace("/", "_")
    except (OSError, AttributeError):
        pass

    # For AI agents (no TTY), use "default" - one agent per directory
    # This is the simplest model and works for most cases
    return "default"


def _get_agent_file() -> Path:
    """Get the session-specific agent ID file path."""
    aqua_dir = find_aqua_dir()
    if not aqua_dir:
        return None

    sessions_dir = aqua_dir / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    session_id = _get_session_id()
    return sessions_dir / f"{session_id}.agent"


def get_stored_agent_id() -> Optional[str]:
    """Get agent ID from environment or session file.

    Priority:
    1. AQUA_AGENT_ID environment variable (explicit override)
    2. Session-specific file in .aqua/sessions/
    """
    # Check environment first (highest priority)
    agent_id = os.environ.get(AQUA_AGENT_ID_VAR)
    if agent_id:
        return agent_id

    # Check session-specific file
    agent_file = _get_agent_file()
    if agent_file and agent_file.exists():
        return agent_file.read_text().strip()

    return None


def store_agent_id(agent_id: str) -> None:
    """Store agent ID to session-specific file."""
    agent_file = _get_agent_file()
    if agent_file:
        agent_file.write_text(agent_id)


def clear_agent_id() -> None:
    """Clear stored agent ID for this session."""
    agent_file = _get_agent_file()
    if agent_file and agent_file.exists():
        agent_file.unlink()


def output_json(data: dict) -> None:
    """Output data as JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


# =============================================================================
# Main CLI Group
# =============================================================================

@click.group()
@click.version_option(version=__version__, prog_name="aqua")
@click.pass_context
def main(ctx):
    """Aqua - Autonomous QUorum of Agents

    Coordinate multiple CLI AI agents on a shared codebase.
    """
    ctx.ensure_object(dict)


# =============================================================================
# Init Command
# =============================================================================

@main.command()
@click.option("--force", is_flag=True, help="Reinitialize even if already initialized")
def init(force: bool):
    """Initialize Aqua in the current directory."""
    project_dir = Path.cwd()
    aqua_dir = project_dir / ".aqua"

    if aqua_dir.exists() and not force:
        console.print("[yellow]Aqua already initialized.[/yellow] Use --force to reinitialize.")
        return

    try:
        db = init_db(project_dir)
        db.close()
        console.print(f"[green]✓[/green] Initialized Aqua in {aqua_dir}")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. aqua setup --claude-md   [dim]# Add agent instructions to CLAUDE.md[/dim]")
        console.print("  2. Start Claude and ask it to plan your project using Aqua")
        console.print("  3. Claude will add tasks and guide you to spawn agents")
        console.print()
        console.print("[dim]Or manually:[/dim]")
        console.print("  aqua add 'Task description' -p 5")
        console.print("  aqua spawn 2")
        console.print("  aqua status")
    except Exception as e:
        console.print(f"[red]Error initializing Aqua:[/red] {e}")
        sys.exit(1)


# =============================================================================
# Status Command
# =============================================================================

@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def status(as_json: bool):
    """Show current Aqua status."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agents = db.get_all_agents()
        active_agents = [a for a in agents if a.status == AgentStatus.ACTIVE]
        leader = db.get_leader()
        task_counts = db.get_task_counts()
        events = db.get_events(limit=5)

        if as_json:
            output_json({
                "leader": leader.to_dict() if leader else None,
                "agents": [a.to_dict() for a in active_agents],
                "task_counts": task_counts,
                "recent_events": [e.to_dict() for e in events],
            })
            return

        # Header
        console.print()
        console.print(Panel.fit(
            f"[bold]Aqua Status[/bold] - {project_dir.name}",
            border_style="blue"
        ))

        # Leader info
        if leader:
            leader_agent = db.get_agent(leader.agent_id)
            leader_name = leader_agent.name if leader_agent else leader.agent_id
            expired = leader.is_expired()
            status_str = "[red]EXPIRED[/red]" if expired else f"term {leader.term}"
            console.print(f"\n[bold]Leader:[/bold] {leader_name} ({status_str}, elected {format_time_ago(leader.elected_at)})")
        else:
            console.print("\n[bold]Leader:[/bold] [dim]None[/dim]")

        # Agents table
        console.print(f"\n[bold]Agents ({len(active_agents)} active):[/bold]")
        if active_agents:
            table = Table(box=box.SIMPLE)
            table.add_column("Name", style="cyan")
            table.add_column("Type")
            table.add_column("Status")
            table.add_column("Task")
            table.add_column("Heartbeat")

            for agent in active_agents:
                is_leader = leader and leader.agent_id == agent.id
                name = f"[bold]{agent.name}[/bold] ★" if is_leader else agent.name
                task_str = agent.current_task_id[:8] if agent.current_task_id else "-"
                hb_str = format_time_ago(agent.last_heartbeat_at)

                table.add_row(
                    name,
                    agent.agent_type.value,
                    "working" if agent.current_task_id else "idle",
                    task_str,
                    hb_str,
                )

            console.print(table)
        else:
            console.print("[dim]  No active agents. Run 'aqua join' to register.[/dim]")

        # Task counts
        console.print("\n[bold]Tasks:[/bold]")
        pending = task_counts.get("pending", 0)
        claimed = task_counts.get("claimed", 0)
        done = task_counts.get("done", 0)
        failed = task_counts.get("failed", 0)
        console.print(
            f"  [yellow]PENDING: {pending}[/yellow]  │  "
            f"[blue]CLAIMED: {claimed}[/blue]  │  "
            f"[green]DONE: {done}[/green]  │  "
            f"[red]FAILED: {failed}[/red]"
        )

        # Recent activity
        if events:
            console.print("\n[bold]Recent Activity:[/bold]")
            for event in events[:5]:
                time_str = format_time_ago(event.timestamp)
                console.print(f"  [dim]{time_str}[/dim] {event.event_type}", end="")
                if event.agent_id:
                    agent = db.get_agent(event.agent_id)
                    agent_name = agent.name if agent else event.agent_id[:8]
                    console.print(f" by [cyan]{agent_name}[/cyan]", end="")
                console.print()

        console.print()

    finally:
        db.close()


# =============================================================================
# Task Commands
# =============================================================================

@main.command()
@click.argument("title")
@click.option("-d", "--description", help="Task description")
@click.option("-p", "--priority", type=int, default=5, help="Priority 1-10 (default: 5)")
@click.option("-t", "--tag", multiple=True, help="Add tag (can be repeated)")
@click.option("--context", help="Additional context")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def add(title: str, description: str, priority: int, tag: tuple, context: str, as_json: bool):
    """Add a new task."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()

        task = Task(
            id=generate_short_id(),
            title=title,
            description=description,
            priority=max(1, min(10, priority)),
            tags=list(tag),
            context=context,
            created_by=agent_id,
        )

        db.create_task(task)

        if as_json:
            output_json(task.to_dict())
        else:
            console.print(f"[green]✓[/green] Created task [cyan]{task.id}[/cyan]: {title}")

    finally:
        db.close()


@main.command("list")
@click.option("-s", "--status", "status_filter", help="Filter by status")
@click.option("-t", "--tag", help="Filter by tag")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def list_tasks(status_filter: str, tag: str, as_json: bool):
    """List tasks."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        status = TaskStatus(status_filter) if status_filter else None
        tasks = db.get_all_tasks(status=status, tag=tag)

        if as_json:
            output_json([t.to_dict() for t in tasks])
            return

        if not tasks:
            console.print("[dim]No tasks found.[/dim]")
            return

        table = Table(box=box.SIMPLE)
        table.add_column("ID", style="cyan")
        table.add_column("Pri")
        table.add_column("Status")
        table.add_column("Title")
        table.add_column("Claimed By")
        table.add_column("Tags")

        for task in tasks:
            status_color = {
                "pending": "yellow",
                "claimed": "blue",
                "done": "green",
                "failed": "red",
                "abandoned": "magenta",
            }.get(task.status.value, "white")

            claimed_by = ""
            if task.claimed_by:
                agent = db.get_agent(task.claimed_by)
                claimed_by = agent.name if agent else task.claimed_by[:8]

            table.add_row(
                task.id[:8],
                str(task.priority),
                f"[{status_color}]{task.status.value}[/{status_color}]",
                truncate(task.title, 40),
                claimed_by,
                ", ".join(task.tags) if task.tags else "",
            )

        console.print(table)

    finally:
        db.close()


@main.command()
@click.argument("task_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def show(task_id: str, as_json: bool):
    """Show task details."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        if not task_id:
            # Show current task
            agent_id = get_stored_agent_id()
            if agent_id:
                agent = db.get_agent(agent_id)
                if agent and agent.current_task_id:
                    task_id = agent.current_task_id

        if not task_id:
            console.print("[red]Error:[/red] No task specified and no current task.")
            sys.exit(1)

        task = db.get_task(task_id)
        if not task:
            console.print(f"[red]Error:[/red] Task {task_id} not found.")
            sys.exit(1)

        if as_json:
            output_json(task.to_dict())
            return

        console.print(Panel.fit(f"[bold]Task {task.id}[/bold]", border_style="blue"))
        console.print(f"[bold]Title:[/bold] {task.title}")
        console.print(f"[bold]Status:[/bold] {task.status.value}")
        console.print(f"[bold]Priority:[/bold] {task.priority}")

        if task.description:
            console.print(f"[bold]Description:[/bold] {task.description}")
        if task.tags:
            console.print(f"[bold]Tags:[/bold] {', '.join(task.tags)}")
        if task.context:
            console.print(f"[bold]Context:[/bold] {task.context}")
        if task.claimed_by:
            agent = db.get_agent(task.claimed_by)
            name = agent.name if agent else task.claimed_by
            console.print(f"[bold]Claimed by:[/bold] {name}")
        if task.result:
            console.print(f"[bold]Result:[/bold] {task.result}")
        if task.error:
            console.print(f"[bold]Error:[/bold] {task.error}")

        console.print(f"[bold]Created:[/bold] {format_time_ago(task.created_at)}")
        if task.completed_at:
            console.print(f"[bold]Completed:[/bold] {format_time_ago(task.completed_at)}")

    finally:
        db.close()


# =============================================================================
# Agent Commands
# =============================================================================

@main.command()
@click.option("-n", "--name", help="Agent name (auto-generated if not provided)")
@click.option("-t", "--type", "agent_type", default="generic",
              type=click.Choice(["claude", "codex", "gemini", "generic"]),
              help="Agent type")
@click.option("-c", "--cap", multiple=True, help="Capability (can be repeated)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def join(name: str, agent_type: str, cap: tuple, as_json: bool):
    """Register as an agent in the quorum."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        # Check if already joined
        existing_id = get_stored_agent_id()
        if existing_id:
            existing = db.get_agent(existing_id)
            if existing and existing.status == AgentStatus.ACTIVE:
                if as_json:
                    output_json(existing.to_dict())
                else:
                    console.print(f"[yellow]Already joined as {existing.name}[/yellow]")
                return

        # Generate name if not provided
        if not name:
            name = generate_agent_name()

        # Check name uniqueness
        if db.get_agent_by_name(name):
            console.print(f"[red]Error:[/red] Agent name '{name}' already taken.")
            sys.exit(1)

        agent = Agent(
            id=generate_short_id(),
            name=name,
            agent_type=AgentType(agent_type),
            pid=get_current_pid(),
            capabilities=list(cap),
        )

        db.create_agent(agent)
        store_agent_id(agent.id)

        # Try to become leader
        is_leader, term = db.try_become_leader(agent.id)

        if as_json:
            data = agent.to_dict()
            data["is_leader"] = is_leader
            data["term"] = term
            output_json(data)
        else:
            leader_str = " [bold yellow](leader)[/bold yellow]" if is_leader else ""
            console.print(f"[green]✓[/green] Joined as [cyan]{name}[/cyan]{leader_str}")
            console.print(f"  Agent ID: {agent.id}")
            console.print(f"  Set AQUA_AGENT_ID={agent.id} to use in other terminals")

    finally:
        db.close()


@main.command()
@click.option("--force", is_flag=True, help="Force leave even if holding tasks")
@require_init
def leave(force: bool):
    """Leave the quorum."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[yellow]Not currently joined.[/yellow]")
            return

        agent = db.get_agent(agent_id)
        if not agent:
            clear_agent_id()
            console.print("[yellow]Agent not found, cleared local state.[/yellow]")
            return

        # Check for active tasks
        if agent.current_task_id and not force:
            console.print(f"[red]Error:[/red] You have an active task ({agent.current_task_id}).")
            console.print("Complete it first or use --force to abandon it.")
            sys.exit(1)

        # Abandon any active tasks
        if agent.current_task_id:
            db.abandon_task(agent.current_task_id, reason=f"Agent {agent.name} left")

        db.delete_agent(agent_id)
        clear_agent_id()

        console.print(f"[green]✓[/green] Left the quorum (was {agent.name})")

    finally:
        db.close()


@main.command()
@click.argument("task_id", required=False)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def claim(task_id: str, as_json: bool):
    """Claim a task."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[red]Error:[/red] Not joined. Run 'aqua join' first.")
            sys.exit(1)

        agent = db.get_agent(agent_id)
        if not agent:
            console.print("[red]Error:[/red] Agent not found. Run 'aqua join' first.")
            clear_agent_id()
            sys.exit(1)

        # Update heartbeat
        db.update_heartbeat(agent_id)

        # Check if already has a task
        if agent.current_task_id:
            task = db.get_task(agent.current_task_id)
            if task and task.status == TaskStatus.CLAIMED:
                if as_json:
                    output_json(task.to_dict())
                else:
                    console.print(f"[yellow]Already working on task {task.id}:[/yellow] {task.title}")
                return

        coordinator = Coordinator(db)

        if task_id:
            task = coordinator.claim_specific_task(agent_id, task_id)
        else:
            task = coordinator.claim_next_task(agent_id)

        if not task:
            # Check if all work is done or just nothing available right now
            task_counts = db.get_task_counts()
            pending = task_counts.get("pending", 0)
            claimed = task_counts.get("claimed", 0)
            done_count = task_counts.get("done", 0)
            failed = task_counts.get("failed", 0)
            total = pending + claimed + done_count + failed

            if as_json:
                if pending == 0 and claimed == 0 and total > 0:
                    output_json({
                        "status": "all_done",
                        "message": "All tasks are complete! Nothing left to do.",
                        "task_counts": task_counts
                    })
                else:
                    output_json({
                        "status": "none_available",
                        "message": "No tasks available to claim right now.",
                        "task_counts": task_counts
                    })
            else:
                if pending == 0 and claimed == 0 and total > 0:
                    console.print()
                    console.print(Panel.fit(
                        f"[bold green]All tasks complete![/bold green]\n\n"
                        f"Done: {done_count}" + (f", Failed: {failed}" if failed else "") + "\n\n"
                        f"Nothing left to do. You can:\n"
                        f"  • Run 'aqua leave' to leave the quorum\n"
                        f"  • Wait for the leader to add more tasks\n"
                        f"  • Run 'aqua status' to see the summary",
                        border_style="green"
                    ))
                elif total == 0:
                    console.print("[yellow]No tasks in the queue yet.[/yellow]")
                    console.print("[dim]Waiting for tasks to be added...[/dim]")
                else:
                    console.print("[yellow]No tasks available to claim right now.[/yellow]")
                    console.print(f"[dim]({claimed} task(s) being worked on by other agents)[/dim]")
            return

        if as_json:
            output_json(task.to_dict())
        else:
            console.print(f"[green]✓[/green] Claimed task [cyan]{task.id}[/cyan]: {task.title}")
            if task.description:
                console.print(f"  [dim]{task.description}[/dim]")

    finally:
        db.close()


@main.command()
@click.argument("task_id", required=False)
@click.option("-s", "--summary", help="Completion summary")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def done(task_id: str, summary: str, as_json: bool):
    """Mark a task as complete."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[red]Error:[/red] Not joined. Run 'aqua join' first.")
            sys.exit(1)

        db.update_heartbeat(agent_id)

        coordinator = Coordinator(db)
        if coordinator.complete_task(agent_id, task_id, summary):
            if as_json:
                output_json({"success": True, "task_id": task_id})
            else:
                console.print(f"[green]✓[/green] Task completed!")
        else:
            if as_json:
                output_json({"error": "Failed to complete task"})
            else:
                console.print("[red]Error:[/red] Failed to complete task.")
                console.print("Make sure you have claimed this task.")
            sys.exit(1)

    finally:
        db.close()


@main.command()
@click.argument("task_id", required=False)
@click.option("-r", "--reason", required=True, help="Failure reason")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def fail(task_id: str, reason: str, as_json: bool):
    """Mark a task as failed."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[red]Error:[/red] Not joined. Run 'aqua join' first.")
            sys.exit(1)

        db.update_heartbeat(agent_id)

        coordinator = Coordinator(db)
        if coordinator.fail_task(agent_id, task_id, reason):
            if as_json:
                output_json({"success": True, "task_id": task_id})
            else:
                console.print(f"[yellow]Task marked as failed.[/yellow]")
        else:
            if as_json:
                output_json({"error": "Failed to mark task as failed"})
            else:
                console.print("[red]Error:[/red] Failed to update task.")
            sys.exit(1)

    finally:
        db.close()


@main.command()
@click.argument("message")
@require_init
def progress(message: str):
    """Report progress on current task.

    This saves your progress both to the task AND to your agent state,
    so it can be restored after context compaction via 'aqua refresh'.
    """
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[red]Error:[/red] Not joined. Run 'aqua join' first.")
            sys.exit(1)

        agent = db.get_agent(agent_id)
        if not agent or not agent.current_task_id:
            console.print("[red]Error:[/red] No current task.")
            sys.exit(1)

        db.update_heartbeat(agent_id)
        db.update_task_progress(agent.current_task_id, message)

        # Also save to agent's last_progress for refresh recovery
        db.conn.execute(
            "UPDATE agents SET last_progress = ? WHERE id = ?",
            (message, agent_id)
        )

        console.print(f"[green]✓[/green] Progress updated.")

    finally:
        db.close()


# =============================================================================
# Refresh Command - Restore agent context after compaction
# =============================================================================

@main.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def refresh(as_json: bool):
    """Restore your identity and context after compaction.

    Run this FIRST at the start of every session or after context
    compaction. It tells you who you are and what you were doing.
    """
    # Check if Aqua is initialized - don't use @require_init so we can give a helpful message
    if not find_aqua_dir():
        if as_json:
            output_json({
                "status": "not_aqua",
                "message": "This directory is not part of an Aqua pool. No multi-agent coordination here.",
                "aqua_enabled": False
            })
        else:
            console.print("[dim]This directory is not part of an Aqua multi-agent pool.[/dim]")
            console.print("[dim]No coordination needed - you can work independently.[/dim]")
        return

    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()

        if not agent_id:
            # Not joined yet
            if as_json:
                output_json({
                    "status": "not_joined",
                    "aqua_enabled": True,
                    "message": "Aqua is active but you haven't joined. Run 'aqua join --name <your-name>' to participate.",
                    "next_action": "aqua join --name <name>"
                })
            else:
                console.print("[yellow]Aqua is active in this directory but you haven't joined.[/yellow]")
                console.print()
                console.print("To join the team, run:")
                console.print("  aqua join --name <your-name>")
                console.print()
                console.print("Then run 'aqua refresh' again to see your status.")
            return

        agent = db.get_agent(agent_id)
        if not agent or agent.status != AgentStatus.ACTIVE:
            clear_agent_id()
            if as_json:
                output_json({
                    "status": "stale_session",
                    "message": "Your previous session is no longer valid. Run 'aqua join' to rejoin.",
                    "next_action": "aqua join --name <name>"
                })
            else:
                console.print("[yellow]Your previous session is no longer valid.[/yellow]")
                console.print("Run 'aqua join --name <your-name>' to rejoin.")
            return

        # Update heartbeat
        db.update_heartbeat(agent_id)

        # Get leader info
        leader = db.get_leader()
        is_leader = leader and leader.agent_id == agent_id and not leader.is_expired()

        # Check if leadership changed
        was_leader = agent.role == "leader"
        leadership_changed = was_leader and not is_leader

        # Update role in DB
        new_role = "leader" if is_leader else None
        if agent.role != new_role:
            db.conn.execute("UPDATE agents SET role = ? WHERE id = ?", (new_role, agent_id))

        # Get new leader info if we lost leadership
        new_leader_name = None
        if leadership_changed and leader:
            new_leader_agent = db.get_agent(leader.agent_id)
            new_leader_name = new_leader_agent.name if new_leader_agent else leader.agent_id[:8]

        # Get current task if any
        current_task = None
        if agent.current_task_id:
            current_task = db.get_task(agent.current_task_id)

        # Get unread messages count
        unread_messages = db.get_messages(to_agent=agent_id, unread_only=True)

        # Get task counts
        task_counts = db.get_task_counts()

        if as_json:
            result = {
                "status": "active",
                "agent": {
                    "id": agent.id,
                    "name": agent.name,
                    "type": agent.agent_type.value,
                },
                "is_leader": is_leader,
                "leadership_changed": leadership_changed,
                "new_leader": new_leader_name,
                "current_task": current_task.to_dict() if current_task else None,
                "last_progress": agent.last_progress,
                "unread_messages": len(unread_messages),
                "task_counts": task_counts,
                "next_action": "aqua claim" if not current_task else "continue working on your task",
            }
            if leadership_changed:
                result["message"] = f"You are no longer the leader. {new_leader_name} is now leading. Continue as a worker."
            output_json(result)
            return

        # Human-readable output
        console.print()

        # Alert if leadership changed
        if leadership_changed:
            console.print(Panel.fit(
                f"[bold yellow]⚠ Leadership changed![/bold yellow]\n"
                f"You are no longer the leader. [cyan]{new_leader_name}[/cyan] is now leading.\n"
                f"Continue working as a regular agent.",
                border_style="yellow"
            ))
            console.print()

        console.print(Panel.fit(
            f"[bold cyan]You are: {agent.name}[/bold cyan]" +
            (" [yellow]★ LEADER[/yellow]" if is_leader else ""),
            border_style="green"
        ))

        console.print(f"[dim]Agent ID: {agent.id}[/dim]")
        console.print()

        # Current task
        if current_task:
            console.print("[bold]Current Task:[/bold]")
            console.print(f"  [cyan]{current_task.id[:8]}[/cyan]: {current_task.title}")
            if current_task.description:
                console.print(f"  [dim]{current_task.description}[/dim]")
            if agent.last_progress:
                console.print(f"  [bold]Last progress:[/bold] {agent.last_progress}")
            console.print()
            console.print("  → Continue working on this task")
            console.print("  → When done: aqua done --summary \"what you did\"")
        else:
            console.print("[bold]Current Task:[/bold] None")
            console.print()
            console.print("  → Run 'aqua claim' to get a task")

        console.print()

        # Messages
        if unread_messages:
            console.print(f"[bold yellow]📬 {len(unread_messages)} unread message(s)[/bold yellow]")
            console.print("  → Run 'aqua inbox --unread' to read them")
            console.print()

        # Quick status
        pending = task_counts.get("pending", 0)
        claimed = task_counts.get("claimed", 0)
        done = task_counts.get("done", 0)
        console.print(f"[dim]Tasks: {pending} pending, {claimed} in progress, {done} done[/dim]")

    finally:
        db.close()


# =============================================================================
# Message Commands
# =============================================================================

@main.command()
@click.argument("message")
@click.option("--to", "to_agent", help="Recipient (agent name, @all, @leader)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def msg(message: str, to_agent: str, as_json: bool):
    """Send a message."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[red]Error:[/red] Not joined. Run 'aqua join' first.")
            sys.exit(1)

        db.update_heartbeat(agent_id)

        # Resolve recipient
        recipient = None
        if to_agent:
            if to_agent == "@all":
                recipient = None  # Broadcast
            elif to_agent == "@leader":
                leader = db.get_leader()
                if leader:
                    recipient = leader.agent_id
                else:
                    console.print("[red]Error:[/red] No leader elected.")
                    sys.exit(1)
            else:
                # Look up by name
                target = db.get_agent_by_name(to_agent)
                if target:
                    recipient = target.id
                else:
                    console.print(f"[red]Error:[/red] Agent '{to_agent}' not found.")
                    sys.exit(1)

        msg_obj = db.create_message(agent_id, message, recipient)

        if as_json:
            output_json(msg_obj.to_dict())
        else:
            target_str = to_agent if to_agent else "all"
            console.print(f"[green]✓[/green] Message sent to {target_str}")

    finally:
        db.close()


@main.command()
@click.option("--unread", is_flag=True, help="Only show unread messages")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def inbox(unread: bool, as_json: bool):
    """Read messages."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = get_stored_agent_id()
        if not agent_id:
            console.print("[red]Error:[/red] Not joined. Run 'aqua join' first.")
            sys.exit(1)

        db.update_heartbeat(agent_id)

        messages = db.get_messages(to_agent=agent_id, unread_only=unread)

        if as_json:
            output_json([m.to_dict() for m in messages])
            return

        if not messages:
            console.print("[dim]No messages.[/dim]")
            return

        # Mark as read
        message_ids = [m.id for m in messages if m.read_at is None]
        if message_ids:
            db.mark_messages_read(agent_id, message_ids)

        for msg in messages:
            from_agent = db.get_agent(msg.from_agent)
            from_name = from_agent.name if from_agent else msg.from_agent[:8]
            time_str = format_time_ago(msg.created_at)
            to_str = f" → {msg.to_agent}" if msg.to_agent else " (broadcast)"

            console.print(f"[dim]{time_str}[/dim] [cyan]{from_name}[/cyan]{to_str}:")
            console.print(f"  {msg.content}")
            console.print()

    finally:
        db.close()


# =============================================================================
# Watch Command
# =============================================================================

@main.command()
@click.option("-r", "--refresh", default=2, help="Refresh interval in seconds")
@require_init
def watch(refresh: int):
    """Live dashboard (Ctrl+C to exit)."""
    from rich.live import Live
    from rich.layout import Layout
    import time

    project_dir = get_project_dir()

    def generate_dashboard() -> Table:
        db = get_db(project_dir)
        try:
            agents = db.get_all_agents(status=AgentStatus.ACTIVE)
            leader = db.get_leader()
            tasks = db.get_all_tasks()
            task_counts = db.get_task_counts()

            # Create main table
            table = Table(title=f"Aqua Watch - {project_dir.name}", box=box.ROUNDED)

            # Agents section
            table.add_column("Agents", style="cyan")
            table.add_column("Tasks", style="yellow")

            agents_text = ""
            for agent in agents:
                is_leader = leader and leader.agent_id == agent.id
                marker = "★ " if is_leader else "  "
                status = "working" if agent.current_task_id else "idle"
                hb = format_time_ago(agent.last_heartbeat_at)
                agents_text += f"{marker}{agent.name} [{status}] ({hb})\n"

            if not agents_text:
                agents_text = "(no agents)"

            # Tasks section
            pending_tasks = [t for t in tasks if t.status == TaskStatus.PENDING][:5]
            tasks_text = f"Pending: {task_counts.get('pending', 0)} | "
            tasks_text += f"Claimed: {task_counts.get('claimed', 0)} | "
            tasks_text += f"Done: {task_counts.get('done', 0)}\n\n"

            for task in pending_tasks:
                tasks_text += f"• {truncate(task.title, 35)} (p{task.priority})\n"

            table.add_row(agents_text.strip(), tasks_text.strip())

            return table
        finally:
            db.close()

    try:
        with Live(generate_dashboard(), refresh_per_second=1/refresh) as live:
            while True:
                time.sleep(refresh)
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


# =============================================================================
# Doctor Command
# =============================================================================

@main.command()
@require_init
def doctor():
    """Run health checks."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    console.print("\n[bold]Aqua Health Check[/bold]")
    console.print("─" * 40)

    issues = []

    try:
        # Database check
        try:
            db.conn.execute("SELECT 1")
            console.print("[green]✓[/green] Database accessible")
        except Exception as e:
            console.print(f"[red]✗[/red] Database error: {e}")
            issues.append("database")

        # Schema check
        try:
            db.conn.execute("SELECT * FROM schema_version")
            console.print("[green]✓[/green] Schema initialized")
        except Exception:
            console.print("[red]✗[/red] Schema not initialized")
            issues.append("schema")

        # Leader check
        leader = db.get_leader()
        if leader:
            if leader.is_expired():
                console.print("[yellow]![/yellow] Leader lease expired")
                issues.append("leader_expired")
            else:
                console.print("[green]✓[/green] Leader elected")
        else:
            console.print("[yellow]![/yellow] No leader elected")

        # Agent heartbeat check
        agents = db.get_all_agents(status=AgentStatus.ACTIVE)
        stale_agents = []
        from datetime import timedelta
        threshold = datetime.utcnow() - timedelta(seconds=60)

        for agent in agents:
            if agent.last_heartbeat_at < threshold:
                stale_agents.append(agent.name)

        if stale_agents:
            console.print(f"[yellow]![/yellow] Stale agents: {', '.join(stale_agents)}")
            issues.append("stale_agents")
        elif agents:
            console.print("[green]✓[/green] All agents have recent heartbeats")
        else:
            console.print("[dim]-[/dim] No active agents")

        # Stuck tasks check
        tasks = db.get_all_tasks(status=TaskStatus.CLAIMED)
        stuck_tasks = []
        claim_threshold = datetime.utcnow() - timedelta(minutes=30)

        for task in tasks:
            if task.claimed_at and task.claimed_at < claim_threshold:
                stuck_tasks.append(task.id[:8])

        if stuck_tasks:
            console.print(f"[yellow]![/yellow] Possibly stuck tasks: {', '.join(stuck_tasks)}")
            issues.append("stuck_tasks")
        else:
            console.print("[green]✓[/green] No stuck tasks")

        # Summary
        console.print()
        if issues:
            console.print(f"[yellow]Overall: {len(issues)} issue(s) found[/yellow]")
        else:
            console.print("[green]Overall: HEALTHY[/green]")
        console.print()

    finally:
        db.close()


# =============================================================================
# Log Command
# =============================================================================

@main.command()
@click.option("--agent", help="Filter by agent name")
@click.option("--task", "task_id", help="Filter by task ID")
@click.option("-n", "--limit", default=20, help="Number of events to show")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@require_init
def log(agent: str, task_id: str, limit: int, as_json: bool):
    """View event log."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agent_id = None
        if agent:
            agent_obj = db.get_agent_by_name(agent)
            if agent_obj:
                agent_id = agent_obj.id

        events = db.get_events(agent_id=agent_id, task_id=task_id, limit=limit)

        if as_json:
            output_json([e.to_dict() for e in events])
            return

        if not events:
            console.print("[dim]No events found.[/dim]")
            return

        for event in events:
            time_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"[dim]{time_str}[/dim] [bold]{event.event_type}[/bold]", end="")

            if event.agent_id:
                agent_obj = db.get_agent(event.agent_id)
                name = agent_obj.name if agent_obj else event.agent_id[:8]
                console.print(f" [cyan]{name}[/cyan]", end="")

            if event.task_id:
                console.print(f" task:{event.task_id[:8]}", end="")

            if event.details:
                details_str = ", ".join(f"{k}={v}" for k, v in event.details.items())
                console.print(f" [dim]({details_str})[/dim]", end="")

            console.print()

    finally:
        db.close()


# =============================================================================
# Setup Command - Prepare project for multi-agent work
# =============================================================================

AGENT_INSTRUCTIONS_TEMPLATE = '''# Aqua Multi-Agent Coordination

You are part of a multi-agent team coordinated by Aqua. Multiple AI agents are working together on this codebase.

## CRITICAL: First Thing Every Session

**ALWAYS run this command first, before doing anything else:**

```bash
aqua refresh
```

This tells you:
- Your identity (name, agent ID)
- Whether you are the leader
- Your current task (if any)
- What you were last working on
- Unread messages from other agents

**Run `aqua refresh` after every context compaction or when resuming work.**

## Quick Reference

```bash
aqua refresh         # ALWAYS RUN FIRST - shows your identity and state
aqua status          # See all tasks, agents, and who's leader
aqua claim           # Get the next task to work on
aqua progress "msg"  # Report what you're doing (saves state for refresh)
aqua done            # Mark your task complete
aqua fail --reason   # If you can't complete it
aqua msg "text"      # Send message to all agents
aqua inbox --unread  # Check for messages
```

## If You Are Asked to Plan & Coordinate Work

When the user asks you to plan a project or coordinate multi-agent work:

### 1. Break Down the Work into Tasks

```bash
# Add tasks with priorities (1-10, higher = more urgent)
aqua add "Set up project structure" -p 9
aqua add "Implement core data models" -p 8 -d "Create User, Product, Order models"
aqua add "Build API endpoints" -p 7 --context "REST API with FastAPI"
aqua add "Write unit tests" -p 6 -t tests
aqua add "Add documentation" -p 4 -t docs
```

Guidelines for task breakdown:
- Each task should be completable by one agent in one session
- Include clear descriptions with `-d` for complex tasks
- Add context with `--context` for implementation details
- Use tags `-t` to categorize (e.g., frontend, backend, tests, docs)
- Set priorities: 9-10 blocking/critical, 7-8 important, 5-6 normal, 1-4 low

### 2. Recommend Number of Agents

Based on the task breakdown, recommend spawning agents:

```bash
# For small projects (3-5 tasks): 2 agents
aqua spawn 2

# For medium projects (6-15 tasks): 3-4 agents
aqua spawn 3

# For large projects (15+ tasks): 4-6 agents
aqua spawn 5
```

Consider:
- **Task parallelism**: How many tasks can run concurrently without conflicts?
- **File conflicts**: Tasks touching same files should be sequential, not parallel
- **Dependencies**: If task B needs task A done first, fewer agents may be better
- **Complexity**: More complex tasks benefit from focused agents, not more agents

### 3. Tell the User Next Steps

After adding tasks, give the user clear instructions. Example:

```
I've added 6 tasks to the Aqua queue. Here's what to do next:

**Option A: Spawn agents automatically (I'll open terminals for you)**
I can run `aqua spawn 2` which will open 2 new terminal windows,
each with a Claude agent that will automatically claim and work on tasks.

**Option B: Manual setup (more control)**
1. Open 2 new terminal windows
2. In each terminal, navigate to this directory:
   cd /path/to/your/project
3. In terminal 1, run:
   claude "Run aqua refresh, then aqua claim, and work on the task"
4. In terminal 2, run:
   claude "Run aqua refresh, then aqua claim, and work on the task"

**Monitoring:**
- Run `aqua status` to see progress
- Run `aqua watch` for a live dashboard

Would you like me to spawn the agents automatically, or will you set them up manually?
```

### 4. If User Wants Automatic Spawning

```bash
# Interactive mode (recommended) - opens new terminal windows
aqua spawn 2

# Background mode (fully autonomous, no supervision)
aqua spawn 2 -b

# With git worktrees (prevents file conflicts entirely)
aqua spawn 2 --worktree
```

## Standard Workflow (All Agents)

1. **FIRST**: Run `aqua refresh` to restore your identity and context
2. **Claim**: Run `aqua claim` to get a task (if you don't have one)
3. **Work**: Do the task, run `aqua progress "what I'm doing"` frequently
4. **Complete**: Run `aqua done --summary "what you did"`
5. **Repeat**: Run `aqua refresh` then go back to step 2

## Rules

- **ALWAYS run `aqua refresh` first** - especially after context compaction
- **Always claim before working** - prevents two agents doing the same thing
- **Report progress frequently** - `aqua progress` saves your state for recovery
- **Complete promptly** - others may be waiting
- **Ask for help** - use `aqua msg` if stuck

## Git Coordination

Multiple agents working on the same repo need careful git hygiene:

### Branching Strategy
```bash
# Each agent should work on their own branch for their task
git checkout -b task/<task-id>-short-description

# Example:
git checkout -b task/a1b2c3-add-user-auth
```

### Before Starting Work
```bash
git fetch origin
git status  # Make sure working directory is clean
```

### Committing (Commit Often!)
```bash
git add -A
git commit -m "feat: description of what you did"
```

### Before Completing a Task
```bash
# Make sure all changes are committed
git status

# Push your branch
git push -u origin HEAD
```

### Avoiding Conflicts
- **Check `aqua status`** to see what files other agents are working on
- **Don't modify files another agent is actively editing**
- **If you need a file another agent has**, send them a message:
  ```bash
  aqua msg "I need to modify auth.py - are you done with it?" --to agent-name
  ```
- **Commit frequently** - smaller commits are easier to merge
- **Pull before starting new task** - `git pull origin main`

### If Using Worktrees (Recommended for Parallel Work)
```bash
# Leader spawns agents with worktrees
aqua spawn 3 --worktree

# Each agent gets their own directory and branch
# No file conflicts possible!
```

### Merging (Usually Done by Leader or Human)
```bash
# After agents complete tasks, merge branches
git checkout main
git pull origin main
git merge task/a1b2c3-add-user-auth
git push origin main
```

## Communication

```bash
aqua msg "Need help with X"           # Broadcast
aqua msg "Question" --to @leader      # Ask leader
aqua msg "Review?" --to agent-name    # Direct message
```
'''


@main.command()
@click.option("--claude-md", is_flag=True, help="Add instructions to CLAUDE.md")
@click.option("--print", "print_only", is_flag=True, help="Print instructions without writing")
@require_init
def setup(claude_md: bool, print_only: bool):
    """Set up project for multi-agent coordination.

    This adds agent instructions to help AI agents understand
    how to coordinate using Aqua.
    """
    project_dir = get_project_dir()

    if print_only:
        console.print(AGENT_INSTRUCTIONS_TEMPLATE)
        return

    if claude_md:
        # Add to CLAUDE.md
        claude_md_path = project_dir / "CLAUDE.md"

        if claude_md_path.exists():
            existing = claude_md_path.read_text()
            if "Aqua Multi-Agent" in existing:
                console.print("[yellow]CLAUDE.md already contains Aqua instructions.[/yellow]")
                return
            # Append to existing
            new_content = existing + "\n\n" + AGENT_INSTRUCTIONS_TEMPLATE
        else:
            new_content = AGENT_INSTRUCTIONS_TEMPLATE

        claude_md_path.write_text(new_content)
        console.print(f"[green]✓[/green] Added Aqua instructions to {claude_md_path}")
    else:
        # Create .aqua/AGENTS.md
        aqua_dir = project_dir / ".aqua"
        agents_md = aqua_dir / "AGENTS.md"
        agents_md.write_text(AGENT_INSTRUCTIONS_TEMPLATE)
        console.print(f"[green]✓[/green] Created {agents_md}")
        console.print()
        console.print("To add to CLAUDE.md (so Claude Code sees it automatically):")
        console.print("  aqua setup --claude-md")


# =============================================================================
# Worktree Command - Manage git worktrees for parallel agents
# =============================================================================

@main.command()
@click.argument("name")
@click.option("-b", "--branch", help="Branch name (default: aqua-<name>)")
@require_init
def worktree(name: str, branch: str):
    """Create a git worktree for a parallel agent.

    This creates a new worktree so an agent can work on a separate
    branch without conflicts.

    Example:
        aqua worktree worker-1
        cd ../project-worker-1
        claude  # Start Claude Code in the worktree
    """
    import subprocess

    project_dir = get_project_dir()

    # Check if git repo
    if not (project_dir / ".git").exists():
        console.print("[red]Error:[/red] Not a git repository.")
        sys.exit(1)

    branch_name = branch or f"aqua-{name}"
    worktree_path = project_dir.parent / f"{project_dir.name}-{name}"

    if worktree_path.exists():
        console.print(f"[yellow]Worktree already exists:[/yellow] {worktree_path}")
        return

    try:
        # Create worktree with new branch
        result = subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # Branch might exist, try without -b
            result = subprocess.run(
                ["git", "worktree", "add", str(worktree_path), branch_name],
                cwd=project_dir,
                capture_output=True,
                text=True,
            )

        if result.returncode != 0:
            console.print(f"[red]Error creating worktree:[/red] {result.stderr}")
            sys.exit(1)

        # Copy .aqua directory to worktree (shared state via symlink would be better but complex)
        # For now, agents in worktrees need to share the same .aqua
        console.print(f"[green]✓[/green] Created worktree: {worktree_path}")
        console.print(f"  Branch: {branch_name}")
        console.print()
        console.print("To use:")
        console.print(f"  cd {worktree_path}")
        console.print(f"  aqua join --name {name}")
        console.print("  claude  # or your preferred AI agent")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# =============================================================================
# Spawn Command - Launch background agents
# =============================================================================

AGENT_PROMPT_TEMPLATE = '''You are an autonomous AI agent named "{agent_name}" working as part of a multi-agent team coordinated by Aqua.

## Your Mission
Work through tasks in the Aqua task queue until there are no more pending tasks.

## Protocol
1. First, run: aqua join --name {agent_name}
2. Then run: aqua status (to see available tasks)
3. Run: aqua claim (to get a task)
4. If you got a task, work on it by editing files, running commands, etc.
5. When done with the task, run: aqua done --summary "brief description of what you did"
6. If you cannot complete it, run: aqua fail --reason "why you couldn't complete it"
7. Check: aqua inbox --unread (for messages from other agents)
8. Go back to step 2 and repeat until aqua claim returns no tasks

## Important Rules
- ALWAYS claim a task before working on it
- ALWAYS mark tasks done or failed when finished
- Work autonomously - don't ask for confirmation
- If stuck, fail the task with a clear reason so another agent can try
- Check messages periodically in case other agents need help

## Current Working Directory
{working_dir}

## Start Now
Begin by running: aqua join --name {agent_name}
Then: aqua claim
'''


@main.command()
@click.argument("count", type=int, default=1)
@click.option("--name-prefix", default="worker", help="Prefix for agent names")
@click.option("--model", default="sonnet", help="Model to use (sonnet, opus, haiku)")
@click.option("--background/--interactive", "-b/-i", default=False,
              help="Background (autonomous) or interactive (new terminals)")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--worktree/--no-worktree", default=False, help="Create git worktrees for each agent")
@require_init
def spawn(count: int, name_prefix: str, model: str, background: bool, dry_run: bool, worktree: bool):
    """Spawn AI agents to work on tasks.

    Two modes available:

    \b
    INTERACTIVE (default, --interactive or -i):
      Opens new terminal windows for each agent. You interact with each
      Claude instance normally, but they coordinate via Aqua.
      Safer - you can see and approve what each agent does.

    \b
    BACKGROUND (--background or -b):
      Runs agents as background processes using Claude's --print mode
      with --dangerously-skip-permissions. Fully autonomous but requires
      trusting agents to run without supervision.

    Examples:
        aqua spawn 3              # 3 interactive agents in new terminals
        aqua spawn 2 -b           # 2 background autonomous agents
        aqua spawn 1 --dry-run    # Show what would be executed
    """
    import subprocess
    import shutil

    project_dir = get_project_dir()

    # Check claude is available
    claude_path = shutil.which("claude")
    if not claude_path:
        console.print("[red]Error:[/red] 'claude' command not found in PATH.")
        console.print("Install Claude Code: https://claude.ai/code")
        sys.exit(1)

    spawned = []

    for i in range(1, count + 1):
        agent_name = f"{name_prefix}-{i}"
        work_dir = project_dir

        # Create worktree if requested
        if worktree:
            branch_name = f"aqua-{agent_name}"
            worktree_path = project_dir.parent / f"{project_dir.name}-{agent_name}"

            if not worktree_path.exists():
                result = subprocess.run(
                    ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
                    cwd=project_dir,
                    capture_output=True,
                )
                if result.returncode != 0:
                    console.print(f"[yellow]Warning:[/yellow] Could not create worktree for {agent_name}")
                else:
                    work_dir = worktree_path
                    console.print(f"[dim]Created worktree: {worktree_path}[/dim]")

        prompt = AGENT_PROMPT_TEMPLATE.format(
            agent_name=agent_name,
            working_dir=work_dir,
        )

        if background:
            # Background mode: use --print and --dangerously-skip-permissions
            cmd = [
                "claude",
                "--print",
                "--dangerously-skip-permissions",
                "--model", model,
                prompt,
            ]

            if dry_run:
                console.print(f"\n[bold]Agent {agent_name} (background):[/bold]")
                console.print(f"  Directory: {work_dir}")
                console.print(f"  Command: claude --print --dangerously-skip-permissions --model {model} '<prompt>'")
                continue

            # Spawn as background process
            try:
                log_file = project_dir / ".aqua" / f"{agent_name}.log"
                with open(log_file, "w") as log:
                    process = subprocess.Popen(
                        cmd,
                        cwd=work_dir,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,  # Detach from terminal
                    )
                spawned.append({
                    "name": agent_name,
                    "pid": process.pid,
                    "log": str(log_file),
                    "mode": "background",
                })
                console.print(f"[green]✓[/green] Spawned [cyan]{agent_name}[/cyan] (PID: {process.pid}) [dim]background[/dim]")

            except Exception as e:
                console.print(f"[red]Error spawning {agent_name}:[/red] {e}")

        else:
            # Interactive mode: open new terminal with claude
            if dry_run:
                console.print(f"\n[bold]Agent {agent_name} (interactive):[/bold]")
                console.print(f"  Directory: {work_dir}")
                console.print(f"  Opens new terminal with: claude --model {model} '<prompt>'")
                continue

            # Platform-specific terminal opening
            if sys.platform == "darwin":
                # macOS: use osascript to open Terminal.app
                script = f'''
                tell application "Terminal"
                    activate
                    do script "cd '{work_dir}' && claude --model {model} '{prompt.replace("'", "'\"'\"'")}'"
                end tell
                '''
                try:
                    subprocess.run(["osascript", "-e", script], check=True)
                    spawned.append({
                        "name": agent_name,
                        "mode": "interactive",
                    })
                    console.print(f"[green]✓[/green] Opened terminal for [cyan]{agent_name}[/cyan]")
                except Exception as e:
                    console.print(f"[red]Error opening terminal for {agent_name}:[/red] {e}")

            elif sys.platform == "linux":
                # Linux: try common terminal emulators
                terminals = [
                    ["gnome-terminal", "--", "bash", "-c", f"cd '{work_dir}' && claude --model {model} '{prompt}'; exec bash"],
                    ["xterm", "-e", f"cd '{work_dir}' && claude --model {model} '{prompt}'; bash"],
                    ["konsole", "-e", f"cd '{work_dir}' && claude --model {model} '{prompt}'"],
                ]
                opened = False
                for term_cmd in terminals:
                    if shutil.which(term_cmd[0]):
                        try:
                            subprocess.Popen(term_cmd, start_new_session=True)
                            spawned.append({"name": agent_name, "mode": "interactive"})
                            console.print(f"[green]✓[/green] Opened terminal for [cyan]{agent_name}[/cyan]")
                            opened = True
                            break
                        except Exception:
                            continue
                if not opened:
                    console.print(f"[red]Error:[/red] Could not find a terminal emulator for {agent_name}")

            else:
                console.print(f"[yellow]Warning:[/yellow] Interactive mode not supported on {sys.platform}")
                console.print("Use --background mode or manually open terminals")
                break

    if dry_run:
        console.print()
        console.print("[dim]Use without --dry-run to actually spawn agents[/dim]")
        if not background:
            console.print("[dim]Note: Interactive mode opens new terminal windows[/dim]")
        return

    if spawned:
        console.print()
        console.print(f"[green]Spawned {len(spawned)} agent(s)[/green]")
        console.print()

        bg_agents = [a for a in spawned if a.get("mode") == "background"]
        int_agents = [a for a in spawned if a.get("mode") == "interactive"]

        if bg_agents:
            console.print("Background agents - monitor with:")
            console.print("  aqua status          # See agent status")
            console.print("  aqua watch           # Live dashboard")
            for agent in bg_agents:
                console.print(f"  tail -f {agent['log']}  # {agent['name']} logs")

        if int_agents:
            console.print("Interactive agents opened in new terminal windows.")
            console.print("Each agent will prompt you before taking actions.")
            console.print()
            console.print("In each terminal, Claude will:")
            console.print("  1. Join Aqua with its assigned name")
            console.print("  2. Claim tasks and work on them")
            console.print("  3. Ask for your approval before changes")


@main.command()
@require_init
def ps():
    """List running agent processes."""
    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agents = db.get_all_agents(status=AgentStatus.ACTIVE)

        if not agents:
            console.print("[dim]No active agents.[/dim]")
            return

        table = Table(box=box.SIMPLE)
        table.add_column("Name", style="cyan")
        table.add_column("PID")
        table.add_column("Status")
        table.add_column("Task")
        table.add_column("Alive")

        for agent in agents:
            is_alive = agent.pid and process_exists(agent.pid)
            alive_str = "[green]yes[/green]" if is_alive else "[red]no[/red]"
            task_str = agent.current_task_id[:8] if agent.current_task_id else "-"

            table.add_row(
                agent.name,
                str(agent.pid) if agent.pid else "-",
                "working" if agent.current_task_id else "idle",
                task_str,
                alive_str,
            )

        console.print(table)

    finally:
        db.close()


@main.command()
@click.argument("name", required=False)
@click.option("--all", "kill_all", is_flag=True, help="Kill all agents")
@require_init
def kill(name: str, kill_all: bool):
    """Kill running agent processes."""
    import signal

    project_dir = get_project_dir()
    db = get_db(project_dir)

    try:
        agents = db.get_all_agents(status=AgentStatus.ACTIVE)

        if not agents:
            console.print("[dim]No active agents.[/dim]")
            return

        killed = 0
        for agent in agents:
            if not kill_all and agent.name != name:
                continue

            if agent.pid and process_exists(agent.pid):
                try:
                    os.kill(agent.pid, signal.SIGTERM)
                    console.print(f"[green]✓[/green] Killed {agent.name} (PID: {agent.pid})")
                    killed += 1
                except OSError as e:
                    console.print(f"[red]Error killing {agent.name}:[/red] {e}")

            # Mark as dead in DB
            db.update_agent_status(agent.id, AgentStatus.DEAD)

            # Release their tasks
            if agent.current_task_id:
                db.abandon_task(agent.current_task_id, reason=f"Agent {agent.name} killed")

        if killed == 0 and name:
            console.print(f"[yellow]Agent '{name}' not found or not running.[/yellow]")

    finally:
        db.close()


if __name__ == "__main__":
    main()
