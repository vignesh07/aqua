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

## Spawning Agents (Important!)

```bash
# Generic spawn (auto-detects available CLI):
aqua spawn 2 -b -y

# REQUIRED when testing/comparing specific agent types:
aqua spawn 2 -b -y --claude           # Only Claude agents
aqua spawn 2 -b -y --codex            # Only Codex agents
aqua spawn 2 -b -y --claude --codex   # 1 Claude + 1 Codex (alternating)
aqua spawn 4 -b -y --claude --codex   # 2 Claude + 2 Codex (alternating)
```

**If the user asks to test, compare, or use specific agent types (Claude, Codex, Gemini),
you MUST use the `--claude`, `--codex`, or `--gemini` flags. Without these flags,
`aqua spawn` will only use whichever single CLI it auto-detects first.**

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
aqua spawn COUNT              # Spawn COUNT agents (auto-detect CLI)
aqua spawn COUNT -b           # Background mode (autonomous) - DANGEROUS
aqua spawn COUNT -b -y        # Background, skip confirmation (use as leader)
aqua spawn COUNT --worktree   # Each agent gets own git worktree

# Specify which AI agent CLIs to use:
aqua spawn 2 --claude         # 2 Claude Code agents
aqua spawn 2 --codex          # 2 Codex CLI agents
aqua spawn 2 --gemini         # 2 Gemini CLI agents

# Mix agents with round-robin assignment:
aqua spawn 4 -b --claude --codex      # 2 Claude + 2 Codex (alternating)
aqua spawn 3 -b --claude --codex      # 2 Claude + 1 Codex
aqua spawn 6 -b --claude --codex --gemini  # 2 of each
```

**IMPORTANT**: When you need specific agent types (e.g., comparing Claude vs Codex,
or testing a particular CLI), you MUST use `--claude`, `--codex`, or `--gemini` flags.
Without these flags, `aqua spawn` auto-detects and uses whichever CLI is available.

**Round-robin**: When multiple CLI flags are specified, agents are assigned in
rotation. `aqua spawn 5 --claude --codex` creates: Claude, Codex, Claude, Codex, Claude.

**WARNING**: Background mode (`-b`) grants agents full autonomous control.
Use `-y` to skip the confirmation prompt (required when spawning programmatically).

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

### 2. Determine Number of Agents

Based on the task breakdown, determine how many agents to spawn:

- **Small projects (3-5 tasks)**: 2 agents
- **Medium projects (6-15 tasks)**: 3-4 agents
- **Large projects (15+ tasks)**: 4-6 agents

Consider:
- **Task parallelism**: How many tasks can run concurrently without conflicts?
- **File conflicts**: Tasks touching same files should be sequential, not parallel
- **Dependencies**: If task B needs task A done first, fewer agents may be better
- **Complexity**: More complex tasks benefit from focused agents, not more agents

### 3. Create Briefing Tasks for New Agents

**IMPORTANT**: Before spawning agents, create a briefing task for each agent. This ensures new agents understand the project context and ground rules before starting work.

```bash
# Create one briefing task per agent you will spawn
# Use priority 10 so agents claim these FIRST
aqua add "BRIEFING: Read before starting" -p 10 -t briefing -d "
Project: [Project name/goal]
Tech stack: [Languages, frameworks, tools]
Ground rules:
- [Rule 1: e.g., All code must have tests]
- [Rule 2: e.g., Use conventional commits]
- [Rule 3: e.g., Lock files before editing]
Key files:
- [Important file 1]
- [Important file 2]
After reading, mark this task done and claim a real task.
"

# Repeat for each agent you plan to spawn
aqua add "BRIEFING: Read before starting" -p 10 -t briefing -d "..."
```

The briefing should include:
- **Project goal**: What we're building
- **Tech stack**: Languages, frameworks, conventions
- **Ground rules**: Testing requirements, commit style, file locking expectations
- **Key files**: Important files to be aware of
- **Dependencies**: What must be done before what

### 4. Spawn Agents

```bash
# Interactive mode (recommended for first-time use) - opens new terminals
aqua spawn 3

# Background mode (autonomous) - prompts for confirmation
aqua spawn 3 -b

# Background mode with auto-confirm (use -y when you're the leader agent)
aqua spawn 3 -b -y

# With git worktrees (for file-conflict-prone work)
aqua spawn 3 --worktree
```

Each spawned agent will:
1. Join and get a unique identity
2. Claim a briefing task first (highest priority)
3. Read the project context and ground rules
4. Mark briefing done
5. Claim real work tasks

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
- **NEVER set AQUA_AGENT_ID or AQUA_SESSION_ID** - Aqua manages your identity automatically. Do NOT prefix commands with these env vars. Just run `aqua <command>` directly.

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

# 1. Initialize Aqua (if not done)
aqua init
aqua setup --claude

# 2. Break down into tasks
aqua add "Set up FastAPI project structure" -p 9 -d "Create main.py, requirements.txt, folder structure"
aqua add "Create Todo model and database" -p 8 -d "SQLite with SQLAlchemy, Todo model with id, title, completed"
aqua add "Implement CRUD endpoints" -p 7 -d "GET /todos, POST /todos, PUT /todos/{id}, DELETE /todos/{id}"
aqua add "Add input validation" -p 6 -d "Pydantic models for request/response"
aqua add "Write tests" -p 5 -t tests -d "pytest tests for all endpoints"
aqua add "Add API documentation" -p 4 -t docs

# 3. Determine agent count (6 tasks, some parallel)
# Tasks 1-2 are sequential (need structure before DB)
# Tasks 3-4 can run in parallel after 1-2
# Tasks 5-6 can run after 3-4
# Decision: 2 agents

# 4. Create briefing tasks (one per agent)
aqua add "BRIEFING: Read before starting" -p 10 -t briefing -d "
Project: Todo REST API
Tech: FastAPI, SQLite, SQLAlchemy, Pydantic, pytest
Ground rules:
- All endpoints need tests
- Use Pydantic for validation
- Lock files before editing (aqua lock <file>)
- Run 'aqua progress' frequently
Structure: src/main.py, src/models.py, src/routes.py, tests/
After reading, run 'aqua done' and claim a real task.
"

aqua add "BRIEFING: Read before starting" -p 10 -t briefing -d "
Project: Todo REST API
Tech: FastAPI, SQLite, SQLAlchemy, Pydantic, pytest
Ground rules:
- All endpoints need tests
- Use Pydantic for validation
- Lock files before editing (aqua lock <file>)
- Run 'aqua progress' frequently
Structure: src/main.py, src/models.py, src/routes.py, tests/
After reading, run 'aqua done' and claim a real task.
"

# 5. Spawn agents
aqua spawn 2
```

## When Stuck

1. Check if another agent can help: `aqua msg "Need help with X" --to @all`
2. Check the task context: `aqua show <task_id>`
3. Fail the task with reason if truly blocked: `aqua fail --reason "Need Y first"`
4. The task will be available for another agent or can be retried later

## Advanced Coordination Patterns

### Pattern 1: Complex Dependency Chains (DAG-like workflows)

Create sophisticated workflows where tasks depend on multiple predecessors:

```bash
# Foundation layer
aqua add "Set up database schema" -p 9
aqua add "Configure authentication" -p 9

# Middle layer - depends on foundation
aqua add "Create user model" -p 8 --after "Set up database schema"
aqua add "Create product model" -p 8 --after "Set up database schema"
aqua add "Build auth middleware" -p 8 --after "Configure authentication"

# API layer - depends on models AND auth
aqua add "User CRUD endpoints" -p 7 --after "Create user model" --after "Build auth middleware"
aqua add "Product CRUD endpoints" -p 7 --after "Create product model" --after "Build auth middleware"

# Integration layer - depends on multiple APIs
aqua add "Order system" -p 6 --after "User CRUD endpoints" --after "Product CRUD endpoints"

# Final layer
aqua add "Integration tests" -p 5 --after "Order system"
```

Agents will automatically respect dependencies - a task won't be claimable until its dependencies are done.

### Pattern 2: File Locking for Conflict Prevention

When multiple agents might touch the same files:

```bash
# Before editing a shared file
aqua lock src/config.py
# ... make your changes ...
aqua unlock src/config.py

# Check what's locked before starting
aqua locks

# In your task workflow:
aqua claim
aqua lock src/models/user.py
aqua progress "Editing user model"
# ... edit the file ...
git add src/models/user.py && git commit -m "Update user model"
aqua unlock src/models/user.py
aqua done --summary "Updated user model with email validation"
```

**Best practice**: Lock files at the start of editing, unlock immediately after committing.

### Pattern 3: Leader Decomposition Pattern

A leader agent can decompose complex work and delegate:

```bash
# Leader claims a high-level task
aqua claim  # Gets "Build authentication system"

# Leader decomposes into subtasks
aqua add "Implement JWT token generation" -p 8 -d "Use PyJWT, 24h expiry"
aqua add "Create login endpoint" -p 8 -d "POST /auth/login, return JWT"
aqua add "Create logout endpoint" -p 7 -d "POST /auth/logout, invalidate token"
aqua add "Add auth middleware" -p 7 -d "Verify JWT on protected routes"
aqua add "Write auth tests" -p 6 -t tests

# Leader spawns workers for subtasks
aqua spawn 3 -b -y

# Leader monitors progress
aqua watch

# When subtasks complete, leader verifies and completes parent
aqua done --summary "Auth system complete: JWT-based auth with login/logout/middleware"
```

### Pattern 4: Blocking Questions for Coordination

When you need input from another agent before proceeding:

```bash
# Ask the leader a question and wait for response
aqua ask "Should I use PostgreSQL or SQLite for the database?" --to @leader --timeout 120

# The leader (or target agent) sees the question in their inbox
aqua inbox --unread

# Leader replies
aqua reply 42 "Use PostgreSQL - we need concurrent writes"

# Your ask command returns with the answer, you continue working
```

### Pattern 5: Parallel Independent Work

For embarrassingly parallel tasks:

```bash
# Add independent tasks (no dependencies)
aqua add "Implement feature A" -p 7 -t feature
aqua add "Implement feature B" -p 7 -t feature
aqua add "Implement feature C" -p 7 -t feature
aqua add "Implement feature D" -p 7 -t feature

# Spawn 4 agents - each grabs one feature
aqua spawn 4 -b -y

# All work in parallel, no conflicts if they touch different files
```

### Pattern 6: Review Workflow

Agent A writes code, Agent B reviews:

```bash
# Add implementation task
aqua add "Implement payment processing" -p 8

# Add review task that depends on implementation
aqua add "Review payment implementation" -p 7 --after "Implement payment processing" -t review

# Add fix task that depends on review
aqua add "Address payment review feedback" -p 6 --after "Review payment implementation"
```

### Pattern 7: Recovery from Failures

Aqua automatically recovers from agent crashes:

```bash
# If an agent dies while holding a task:
# - After 5 minutes without heartbeat, agent is marked dead
# - Its claimed tasks return to PENDING
# - Other agents can claim them

# Manual recovery if needed:
aqua recover              # Recover orphaned tasks
aqua doctor --fix         # Full health check and repair

# Check system health
aqua doctor
```

### Pattern 8: Mixed AI Agent Teams

Leverage different AI strengths:

```bash
# Claude for complex reasoning tasks
aqua add "Design system architecture" -p 9 -t architecture

# Codex for implementation
aqua add "Implement data layer" -p 8 -t implementation
aqua add "Implement API layer" -p 8 -t implementation

# Spawn mixed team
aqua spawn 3 -b -y --claude --codex  # 2 Claude + 1 Codex (round-robin)
```

## JSON Mode for Programmatic Access

All commands support `--json` for scripting:

```bash
# Get structured output
aqua status --json | jq '.tasks[] | select(.status == "pending")'
aqua claim --json | jq '.id'

# Or set globally
export AQUA_JSON=1
aqua status | jq '.agents'
```

## Summary: What Makes Aqua Powerful

1. **Zero setup**: `pip install aqua-coord && aqua init` - no Redis, no Docker
2. **Full dependency DAGs**: Complex workflows with `--depends-on` and `--after`
3. **File locking**: Prevent conflicts with `aqua lock/unlock`
4. **Inter-agent messaging**: Broadcast, direct, and blocking ask/reply
5. **Auto-recovery**: Dead agents detected, orphaned tasks reclaimed
6. **Mixed AI teams**: Claude + Codex + Gemini with round-robin assignment
7. **Git-native**: Works with your existing git workflow

You have everything needed for sophisticated multi-agent coordination. Use it!
