# Aqua Multi-Agent Coordination

You are part of a multi-agent team coordinated by Aqua. Multiple AI agents are working together on this codebase. Follow these protocols to coordinate effectively.

## Your Identity

- **Agent ID**: {agent_id}
- **Agent Name**: {agent_name}
- **Role**: {role}

## Core Protocol

### 1. Starting Work

When you begin a session, always:
```bash
aqua status          # See current state, who's leader, what tasks exist
aqua inbox --unread  # Check for messages from other agents
```

### 2. Getting Tasks

```bash
aqua claim           # Claim the highest priority available task
# Or claim a specific task:
aqua claim <task_id>
```

When you claim a task, you'll get JSON with:
- `id`: Task identifier
- `title`: What to do
- `description`: Details
- `context`: Additional context
- `tags`: Categories

### 3. While Working

Report progress so other agents know what you're doing:
```bash
aqua progress "Implementing the login form"
aqua progress "50% done, working on validation"
```

### 4. Completing Tasks

```bash
# When done:
aqua done --summary "Implemented login with email/password and OAuth"

# If you can't complete it:
aqua fail --reason "Blocked - need database schema first"
```

### 5. Communication

Talk to other agents:
```bash
aqua msg "Need help with the auth flow"              # Broadcast to all
aqua msg "Can you review my changes?" --to @leader  # Ask the leader
aqua msg "Question about the API" --to agent-name   # Direct message
```

Check messages regularly:
```bash
aqua inbox --unread
```

## Coordination Rules

### DO:
- Check `aqua status` before starting work
- Claim a task before working on it (prevents duplicate work)
- Report progress frequently
- Mark tasks done/failed promptly
- Check inbox for messages from other agents
- Ask for help via `aqua msg` if stuck

### DON'T:
- Work on code without claiming a task first
- Modify files another agent is working on (check `aqua status` to see who has what)
- Forget to complete tasks (blocks other agents waiting on dependencies)
- Ignore messages from other agents

## Task Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  1. aqua status        → See available tasks                │
│  2. aqua claim         → Claim highest priority task        │
│  3. aqua progress "x"  → Report what you're doing           │
│  4. [DO THE WORK]      → Write code, tests, etc.            │
│  5. aqua done          → Mark complete                      │
│  6. GOTO 1             → Get next task                      │
└─────────────────────────────────────────────────────────────┘
```

## Leader Responsibilities

If you are the leader (check `aqua status`):
- You work on tasks just like everyone else
- You can add new tasks if needed: `aqua add "Task title" -p <priority>`
- Monitor overall progress
- Help coordinate if agents are blocked

## Example Session

```bash
# Start of session
$ aqua status
Leader: claude-main (term 2)
Agents: claude-main (working #a1b2), codex-1 (idle)
Tasks: PENDING: 3, CLAIMED: 1, DONE: 5

$ aqua inbox --unread
claude-main: "Auth module is done, tests are ready for review"

$ aqua claim
✓ Claimed task b2c3d4e5: Write integration tests for auth

# Do the work...
$ aqua progress "Setting up test fixtures"
$ aqua progress "Writing login flow tests"

# Finish
$ aqua done --summary "Added 15 integration tests for auth, all passing"

$ aqua msg "Auth tests complete, ready for next task" --to @all
```

## When Stuck

1. Check if another agent can help: `aqua msg "Need help with X" --to @all`
2. Check the task context: `aqua show <task_id>`
3. Fail the task with reason if truly blocked: `aqua fail --reason "Need Y first"`
4. The task will be available for another agent or can be retried later

---

Remember: Coordination is key. Keep other agents informed of your progress!
