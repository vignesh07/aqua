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
)

console = Console()

# Environment variable for storing agent ID
AQUA_AGENT_ID_VAR = "AQUA_AGENT_ID"
AQUA_AGENT_FILE = ".aqua/agent_id"


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


def get_stored_agent_id() -> Optional[str]:
    """Get agent ID from environment or file."""
    # Check environment first
    agent_id = os.environ.get(AQUA_AGENT_ID_VAR)
    if agent_id:
        return agent_id

    # Check file
    aqua_dir = find_aqua_dir()
    if aqua_dir:
        agent_file = aqua_dir / "agent_id"
        if agent_file.exists():
            return agent_file.read_text().strip()

    return None


def store_agent_id(agent_id: str) -> None:
    """Store agent ID to file."""
    aqua_dir = find_aqua_dir()
    if aqua_dir:
        agent_file = aqua_dir / "agent_id"
        agent_file.write_text(agent_id)


def clear_agent_id() -> None:
    """Clear stored agent ID."""
    aqua_dir = find_aqua_dir()
    if aqua_dir:
        agent_file = aqua_dir / "agent_id"
        if agent_file.exists():
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
        console.print("\nNext steps:")
        console.print("  aqua add 'Your first task'")
        console.print("  aqua join --name my-agent")
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
            if as_json:
                output_json({"error": "No task available"})
            else:
                console.print("[yellow]No tasks available to claim.[/yellow]")
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
    """Report progress on current task."""
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

        console.print(f"[green]✓[/green] Progress updated.")

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


if __name__ == "__main__":
    main()
