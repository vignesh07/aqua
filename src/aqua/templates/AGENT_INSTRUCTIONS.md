# Aqua Multi-Agent Coordination

You are part of a multi-agent team coordinated by Aqua. Multiple AI agents are working together on this codebase. Follow these protocols to coordinate effectively.

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

## Your Identity

After running `aqua refresh`, you'll know:
- **Agent Name**: Your unique identifier in the team
- **Role**: Whether you're the leader or a worker
- **Current Task**: What you should be working on

## Core Protocol

### 1. Starting Work (EVERY SESSION)

```bash
aqua refresh         # ALWAYS RUN FIRST - restores your identity and context
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

Report progress so other agents know what you're doing AND so you can recover after compaction:
```bash
aqua progress "Implementing the login form"
aqua progress "50% done, working on validation"
```

**Important**: `aqua progress` saves your state so `aqua refresh` can restore it!

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
- **ALWAYS run `aqua refresh` first** - especially after context compaction
- Check `aqua status` before starting work
- Claim a task before working on it (prevents duplicate work)
- Report progress frequently with `aqua progress`
- Mark tasks done/failed promptly
- Check inbox for messages from other agents
- Ask for help via `aqua msg` if stuck

### DON'T:
- Work on code without claiming a task first
- Modify files another agent is working on (check `aqua status` to see who has what)
- Forget to complete tasks (blocks other agents waiting on dependencies)
- Ignore messages from other agents
- Forget to run `aqua refresh` after context compaction

## Task Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  1. aqua refresh     → Restore your identity (ALWAYS FIRST) │
│  2. aqua claim       → Get a task to work on                │
│  3. aqua progress    → Report what you're doing             │
│  4. [DO THE WORK]    → Write code, tests, etc.              │
│  5. aqua done        → Mark complete                        │
│  6. GOTO 1           → Refresh and get next task            │
└─────────────────────────────────────────────────────────────┘
```

## Leader Responsibilities

If you are the leader (check `aqua refresh`):
- You work on tasks just like everyone else
- You can add new tasks if needed: `aqua add "Task title" -p <priority>`
- Monitor overall progress
- Help coordinate if agents are blocked

## Example Session

```bash
# Start of session (or after context compaction)
$ aqua refresh
┌───────────────────────────────────┐
│ You are: claude-main ★ LEADER    │
└───────────────────────────────────┘
Agent ID: a1b2c3d4

Current Task:
  f5e6d7c8: Implement user authentication
  Last progress: Setting up OAuth providers

  → Continue working on this task
  → When done: aqua done --summary "what you did"

📬 2 unread message(s)
  → Run 'aqua inbox --unread' to read them

Tasks: 3 pending, 1 in progress, 5 done

$ aqua inbox --unread
codex-1: "Auth module tests are ready for review"
gemini-2: "Can someone help with the API docs?"

# Continue working...
$ aqua progress "Finishing OAuth Google provider"

# Complete the task
$ aqua done --summary "Added OAuth with Google and GitHub providers"

# Get next task
$ aqua refresh
$ aqua claim
```

## When Stuck

1. Check if another agent can help: `aqua msg "Need help with X" --to @all`
2. Check the task context: `aqua show <task_id>`
3. Fail the task with reason if truly blocked: `aqua fail --reason "Need Y first"`
4. The task will be available for another agent or can be retried later

---

Remember:
- **ALWAYS run `aqua refresh` first** - it restores your identity after context compaction
- **Report progress often** - `aqua progress` saves state for recovery
- Coordination is key. Keep other agents informed!
