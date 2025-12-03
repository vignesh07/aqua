# Aqua Multi-Agent Coordination

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

## Full Command Reference

### Core Commands
```bash
aqua init                     # Initialize Aqua in this directory
aqua status                   # Show all tasks, agents, leader, and locks
aqua refresh                  # Restore agent identity after context reset
```

### Task Management
```bash
aqua add "Title" [OPTIONS]    # Add a new task
  -d, --description TEXT      # Task description
  -p, --priority 1-10         # Priority (higher = more urgent, default: 5)
  -t, --tag TAG               # Add tag (repeatable)
  --context TEXT              # Additional context
  --depends-on ID             # Task ID this depends on (repeatable)
  --after "Title"             # Task title this depends on (fuzzy match)

aqua claim [TASK_ID]          # Claim next pending task (or specific task)
aqua show [TASK_ID]           # Show task details
aqua done [--summary TEXT]    # Mark current task complete
aqua fail --reason TEXT       # Mark current task as failed
aqua progress "message"       # Report progress on current task
```

### Agent Management
```bash
aqua join [-n NAME]           # Register as an agent
aqua leave                    # Leave the quorum
aqua ps                       # Show all agent processes
aqua kill [NAME|--all]        # Kill agent(s)
```

### File Locking (Prevent Conflicts)
```bash
aqua lock <file>              # Lock a file for exclusive editing
aqua unlock <file>            # Release a file lock
aqua locks                    # Show all current file locks
```

### Communication
```bash
aqua msg "text"               # Broadcast message to all agents
aqua msg "text" --to NAME     # Direct message to agent
aqua msg "text" --to @leader  # Message the leader
aqua inbox                    # Show all messages
aqua inbox --unread           # Show only unread messages
aqua ask "question" --to NAME # Ask and wait for reply (blocking)
aqua reply <msg_id> "answer"  # Reply to a question
```

### Monitoring
```bash
aqua watch                    # Live dashboard (Ctrl+C to exit)
aqua logs                     # Tail event stream (like tail -f)
aqua logs --agent NAME        # Tail events for specific agent
aqua logs --json              # Machine-readable event stream
aqua log [-n LIMIT]           # View historical events
```

### Spawning Agents
```bash
aqua spawn COUNT              # Spawn COUNT agents in new terminals
aqua spawn COUNT -b           # Spawn in background (autonomous)
aqua spawn COUNT --worktree   # Each agent gets own git worktree
```

### Utility
```bash
aqua doctor                   # Check system health
aqua setup --all              # Add instructions to agent MD files
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

### 3. Spawn Agents

```bash
# Interactive mode (recommended for first-time use) - opens new terminals
aqua spawn 3

# Background mode (autonomous, less supervision)
aqua spawn 3 -b

# With git worktrees (for file-conflict-prone work)
aqua spawn 3 --worktree
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

## Communication

```bash
aqua msg "Need help with X"           # Broadcast
aqua msg "Question" --to @leader      # Ask leader
aqua msg "Review?" --to agent-name    # Direct message
```

## Leader Responsibilities

If you are the leader (shown in `aqua refresh`):
- You work on tasks just like everyone else
- You can add new tasks if needed: `aqua add "Task title" -p <priority>`
- Monitor overall progress with `aqua status`
- Help coordinate if agents are blocked

## Example Planning Session

```bash
# User asks: "Build me a REST API for a todo app"

# 1. Initialize Aqua
aqua init
aqua setup --claude-md

# 2. Break down into tasks
aqua add "Set up FastAPI project structure" -p 9 -d "Create main.py, requirements.txt, folder structure"
aqua add "Create Todo model and database" -p 8 -d "SQLite with SQLAlchemy, Todo model with id, title, completed"
aqua add "Implement CRUD endpoints" -p 7 -d "GET /todos, POST /todos, PUT /todos/{id}, DELETE /todos/{id}"
aqua add "Add input validation" -p 6 -d "Pydantic models for request/response"
aqua add "Write tests" -p 5 -t tests -d "pytest tests for all endpoints"
aqua add "Add API documentation" -p 4 -t docs

# 3. Recommend agents (6 tasks, some can run in parallel)
# Tasks 1-2 are sequential (need structure before DB)
# Tasks 3-4 can run in parallel after 1-2
# Tasks 5-6 can run after 3-4
# Recommend: 2-3 agents

aqua spawn 2  # Interactive mode, user can watch
```

## When Stuck

1. Check if another agent can help: `aqua msg "Need help with X" --to @all`
2. Check the task context: `aqua show <task_id>`
3. Fail the task with reason if truly blocked: `aqua fail --reason "Need Y first"`
4. The task will be available for another agent or can be retried later
