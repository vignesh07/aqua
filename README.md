# Aqua - Autonomous QUorum of Agents

[![PyPI version](https://badge.fury.io/py/aqua-coord.svg)](https://badge.fury.io/py/aqua-coord)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Aqua** is a lightweight, agent-agnostic coordinator for CLI AI agents. It enables multiple AI agents (Claude Code, Codex CLI, Gemini CLI, or any CLI tool) running in separate terminal sessions to collaborate on tasks within a shared codebase. Built with Claude ❤️

![Aqua in action](https://vignesh07.github.io/aqua/assets/images/aqua-demo.gif)

## Why Aqua?

When working with AI coding agents, you often want multiple agents working in parallel on different tasks. But without coordination, agents can:
- Work on the same task simultaneously
- Edit the same files and create conflicts
- Lack visibility into what other agents are doing

Aqua solves this by providing:
- **Shared task queue** with atomic claiming
- **File locking** to prevent conflicts
- **Inter-agent messaging** for coordination
- **Live monitoring** to see all agent activity

## Features

- **Task Queue**: Priority-based task management with dependencies
- **Circular Dependency Detection**: Prevents deadlocks by rejecting cyclic task dependencies
- **File Locking**: Prevent multiple agents from editing the same file
- **Blocking Messages**: Ask questions and wait for replies from other agents
- **Live Monitoring**: Real-time dashboard and event stream
- **Leader Election**: Automatic coordination with one agent assuming leadership
- **Crash Recovery**: Automatic detection of dead agents and task reassignment (heartbeat-based)
- **Agent Agnostic**: Works with Claude Code, Codex CLI, Gemini CLI, or any CLI tool
- **Zero External Dependencies**: Uses SQLite - no Redis, Docker, or external services
- **JSON Mode**: Full `--json` support and `AQUA_JSON=1` env var for programmatic access

## Installation

```bash
pip install aqua-coord
```

## Quick Start

### 1. Initialize Aqua in your project

```bash
cd your-project
aqua init
aqua setup --all  # Add instructions to CLAUDE.md, AGENTS.md, GEMINI.md
```

### 2. Add tasks with dependencies

```bash
aqua add "Set up project structure" -p 9
aqua add "Implement data models" -p 8 --after "Set up project structure"
aqua add "Build API endpoints" -p 7 --depends-on abc123
aqua add "Write tests" -p 6 -t tests
```

### 3. Spawn agents automatically

```bash
# Open 3 new terminal windows, each with an AI agent
aqua spawn 3

# Or run agents in background (fully autonomous)
# ⚠️  Prompts for confirmation - agents get full permissions!
aqua spawn 3 -b

# Use a specific CLI (auto-detects by default)
aqua spawn 2 --codex

# Mix agents with round-robin assignment
aqua spawn 4 -b --claude --codex  # 2 Claude + 2 Codex

# Skip confirmation (for programmatic use or leader agents)
aqua spawn 2 -b -y
```

> **⚠️ Background Mode Warning**: The `-b` flag grants agents full autonomous control using dangerous flags like `--dangerously-skip-permissions` (Claude) and `--approval-mode full-auto` (Codex). Agents can read, write, and execute ANY code without asking. Use `-y` to skip the confirmation prompt.

### 4. Monitor progress

```bash
aqua status   # Show current state
aqua watch    # Live dashboard (updates every 2s)
aqua logs     # Tail event stream in real-time
```

### Alternative: Let the Agent Do It

After running `aqua setup --all`, you can simply start your AI agent and ask it to plan the project:

```bash
aqua init
aqua setup --all

# Start your AI agent (Claude Code, Codex, Gemini)
claude  # or: codex, gemini

# Then ask:
> "Plan this project and spawn workers to build it"
```

The agent reads the instructions from CLAUDE.md (or AGENTS.md/GEMINI.md), understands Aqua's capabilities, and handles task breakdown, agent spawning, and coordination autonomously.

## Complete Command Reference

### Core Commands

| Command | Description |
|---------|-------------|
| `aqua init` | Initialize Aqua in current directory |
| `aqua status` | Show dashboard with agents, tasks, and leader info |
| `aqua refresh` | Restore agent identity after context reset |

### Task Management

| Command | Description |
|---------|-------------|
| `aqua add <title>` | Add a new task |
| `aqua show [task_id]` | Show task details |
| `aqua claim [task_id]` | Claim next pending task (or specific task) |
| `aqua done [--summary]` | Mark current task complete |
| `aqua fail --reason` | Mark current task as failed |
| `aqua progress <msg>` | Report progress (saves state for refresh) |

**Options for `aqua add`:**
```bash
aqua add "Title" \
  -d "Description" \
  -p 8 \                      # Priority 1-10 (higher = more urgent)
  -t backend \                # Tag (repeatable)
  --context "Use FastAPI" \   # Additional context
  --depends-on abc123 \       # Depends on task ID (repeatable)
  --after "Setup project"     # Depends on task by title match
```

### Agent Management

| Command | Description |
|---------|-------------|
| `aqua join [-n name]` | Register as an agent |
| `aqua leave` | Leave the quorum |
| `aqua ps` | Show all agent processes |
| `aqua kill [name\|--all]` | Kill agent(s) |
| `aqua spawn <count>` | Spawn AI agents in new terminals |

### File Locking

Prevent multiple agents from editing the same file:

```bash
aqua lock src/handlers.py     # Lock a file for exclusive editing
aqua unlock src/handlers.py   # Release a file lock
aqua locks                    # Show all current file locks
```

### Communication

```bash
# Fire-and-forget messages
aqua msg "Need help with auth" --to worker-2
aqua msg "Starting deployment" --to @all
aqua inbox --unread

# Blocking questions (waits for reply)
aqua ask "Should I use Redis or SQLite?" --to @leader --timeout 60
# Other agent replies with:
aqua reply 42 "Use SQLite, it's simpler"
```

### Monitoring & Recovery

```bash
aqua watch                    # Live dashboard (Ctrl+C to exit)
aqua logs                     # Tail event stream (like tail -f)
aqua logs --agent worker-1    # Filter by agent
aqua logs --json              # Machine-readable output
aqua log -n 50                # View last 50 events
aqua doctor                   # Run health checks
aqua doctor --fix             # Fix issues (recover orphaned tasks)
aqua recover                  # Recover tasks from dead agents
```

### Setup

```bash
aqua setup --claude           # Add instructions to CLAUDE.md
aqua setup --codex            # Add instructions to AGENTS.md
aqua setup --gemini           # Add instructions to GEMINI.md
aqua setup --all              # All of the above
aqua setup --print            # Print instructions without writing
```

## Workflow Example

Here's a typical multi-agent workflow:

```bash
# 1. Initialize and add tasks
aqua init
aqua setup --all

aqua add "Set up FastAPI project" -p 9
aqua add "Create User model" -p 8 --after "Set up FastAPI project"
aqua add "Build /users endpoints" -p 7 --after "Create User model"
aqua add "Write API tests" -p 6 -t tests

# 2. Spawn 2 agents
aqua spawn 2

# 3. In another terminal, monitor progress
aqua watch
```

Each spawned agent will:
1. Join with a unique name (worker-1, worker-2, etc.)
2. Claim tasks respecting dependencies
3. Lock files before editing
4. Report progress periodically
5. Mark tasks done when complete
6. Claim the next available task

## JSON Mode

All commands support `--json` for programmatic access:

```bash
# Per-command
aqua status --json | jq .tasks
aqua claim --json | jq .id
aqua doctor --json | jq .healthy

# Global mode (affects all commands)
export AQUA_JSON=1
aqua status | jq .agents
```

## Programmatic Integration

```python
import subprocess
import json

def aqua(args):
    result = subprocess.run(
        ['aqua'] + args + ['--json'],
        capture_output=True, text=True
    )
    return json.loads(result.stdout) if result.returncode == 0 else None

# Join and work on tasks
agent = aqua(['join', '--name', 'my-bot'])
while True:
    task = aqua(['claim'])
    if not task:
        break
    # Do work...
    aqua(['progress', 'Working on implementation'])
    aqua(['done', '--summary', 'Implemented feature X'])
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Aqua CLI (aqua)                        │
├─────────────────────────────────────────────────────────────┤
│  Task Queue │ File Locks │ Messages │ Agent Registry        │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Coordinator Core                          │
│  • Leader Election (lease-based with fencing tokens)        │
│  • Task Scheduler (priority + dependencies)                 │
│  • Crash Recovery (heartbeat + PID monitoring)              │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   SQLite Database                            │
│                 .aqua/aqua.db (WAL mode)                    │
└─────────────────────────────────────────────────────────────┘
```

## Supported Agents

| CLI | Instruction File |
|-----|------------------|
| [Claude Code](https://claude.ai/code) | `CLAUDE.md` |
| [Codex CLI](https://github.com/openai/codex-cli) | `AGENTS.md` |
| [Gemini CLI](https://github.com/google/gemini-cli) | `GEMINI.md` |

Aqua auto-detects which CLI is available when using `aqua spawn`. Each CLI uses its own default model - override with `--model` if needed.

## Development

```bash
# Clone and install
git clone https://github.com/vignesh07/aqua.git
cd aqua
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=aqua

# Lint
ruff check src/
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Not accepting contributions at the moment.

---

**Made for the multi-agent future.**
