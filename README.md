# Aqua - Autonomous QUorum of Agents

[![PyPI version](https://badge.fury.io/py/aqua-coord.svg)](https://badge.fury.io/py/aqua-coord)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, agent-agnostic coordinator for CLI AI agents. Aqua enables multiple AI agents (Claude Code, Codex, Gemini CLI, or any CLI tool) running in separate terminal sessions to collaborate on tasks within a shared codebase.

## Features

- **Leader Election**: Automatic coordination with one agent assuming leadership
- **Task Management**: Shared task queue with atomic claiming and priority-based scheduling
- **Message Passing**: Inter-agent communication via broadcast or direct messages
- **Crash Recovery**: Automatic detection of dead agents and task reassignment
- **Agent Agnostic**: Works with any CLI agent that can execute shell commands
- **Zero External Dependencies**: Uses SQLite (built into Python) - no Redis, Docker, or external services

## Installation

```bash
pip install aqua-coord
```

## Quick Start

### 1. Initialize Aqua in your project

```bash
cd your-project
aqua init
```

### 2. Add some tasks

```bash
aqua add "Implement user authentication"
aqua add "Write unit tests" --priority 8
aqua add "Update documentation" --tag docs
```

### 3. Start agents in separate terminals

**Terminal 1:**
```bash
aqua join --name claude-main --type claude
aqua claim
# Work on the task...
aqua done --summary "Implemented OAuth2 authentication"
```

**Terminal 2:**
```bash
aqua join --name codex-helper --type codex
aqua claim
# Work on the task...
aqua done --summary "Added test coverage"
```

### 4. Monitor progress

```bash
aqua status   # Show current state
aqua watch    # Live dashboard
```

## CLI Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `aqua init` | Initialize Aqua in current directory |
| `aqua status` | Show dashboard with agents, tasks, and leader info |
| `aqua watch` | Live updating dashboard |
| `aqua doctor` | Run health checks |

### Task Management

| Command | Description |
|---------|-------------|
| `aqua add <title>` | Add a new task |
| `aqua list` | List all tasks |
| `aqua show <task_id>` | Show task details |

Options for `aqua add`:
- `-d, --description` - Task description
- `-p, --priority` - Priority 1-10 (default: 5)
- `-t, --tag` - Add tag (repeatable)
- `--context` - Additional context

### Agent Commands

| Command | Description |
|---------|-------------|
| `aqua join` | Register as an agent |
| `aqua leave` | Leave the quorum |
| `aqua claim [task_id]` | Claim next task or specific task |
| `aqua done [task_id]` | Mark task as complete |
| `aqua fail [task_id]` | Mark task as failed |
| `aqua progress <msg>` | Report progress on current task |

Options for `aqua join`:
- `-n, --name` - Agent name (auto-generated if omitted)
- `-t, --type` - Agent type: claude, codex, gemini, generic

### Communication

| Command | Description |
|---------|-------------|
| `aqua msg <message>` | Send a message |
| `aqua inbox` | Read messages |

Options for `aqua msg`:
- `--to` - Recipient: agent-name, @all (broadcast), @leader

## How It Works

### Leader Election

Aqua uses lease-based leader election with fencing tokens:

1. First agent to join becomes leader
2. Leader renews lease every 10 seconds (lease duration: 30 seconds)
3. If leader's lease expires, a new leader is elected
4. Term numbers (fencing tokens) prevent stale operations

### Task Claiming

Tasks are claimed atomically using SQLite transactions:

```bash
# Claim highest priority available task
aqua claim

# Claim specific task
aqua claim abc123
```

### Crash Recovery

The leader periodically checks for crashed agents:

1. Agents with heartbeats older than 60 seconds are considered potentially dead
2. Process existence is verified via PID
3. Dead agents are marked and their tasks released
4. Released tasks can be reclaimed by other agents

## Agent Integration

Aqua works with any CLI agent through simple shell commands:

### For Claude Code

Add to your agent's instructions:

```markdown
## Aqua Coordination

You are part of a multi-agent team coordinated by Aqua.

1. Check status: `aqua status`
2. Claim a task: `aqua claim` (returns JSON with --json flag)
3. Report progress: `aqua progress "Working on X..."`
4. Complete task: `aqua done --summary "What was accomplished"`
5. Send message: `aqua msg "Need help" --to @leader`
6. Read messages: `aqua inbox --unread`
```

### Programmatic Integration

```python
import subprocess
import json

def aqua(args):
    result = subprocess.run(['aqua'] + args + ['--json'], capture_output=True, text=True)
    return json.loads(result.stdout) if result.returncode == 0 else None

# Join the quorum
agent = aqua(['join', '--name', 'my-agent'])

# Claim and work on tasks
while True:
    task = aqua(['claim'])
    if task:
        # Do work...
        aqua(['done', '--summary', 'Completed task'])
```

## Configuration

Optional `.aqua/config.yaml`:

```yaml
# Timing (all optional)
leader_lease_seconds: 30
heartbeat_interval_seconds: 10
agent_dead_threshold_seconds: 60
task_claim_timeout_seconds: 600

# Behavior
auto_recover_tasks: true
max_task_retries: 3
```

## JSON Output

All commands support `--json` flag for programmatic access:

```bash
aqua status --json | jq .leader.name
aqua list --json | jq '.[] | select(.status == "pending")'
aqua claim --json | jq .id
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Aqua CLI (aqua)                       │
├─────────────────────────────────────────────────────────┤
│  Commands: init, add, list, status, join, claim, ...    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  Coordinator Core                        │
│  • Leader Election (lease-based with fencing tokens)    │
│  • Task Scheduler (priority-based, atomic claiming)     │
│  • Crash Recovery (heartbeat + PID monitoring)          │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                 SQLite Database                          │
│               .aqua/aqua.db (WAL mode)                  │
└─────────────────────────────────────────────────────────┘
```

## Development

```bash
# Clone the repository
git clone https://github.com/vignesh07/aqua.git
cd aqua

# Install in development mode
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

Contributions are welcome! Please read the [DESIGN.md](DESIGN.md) document for architecture details.
