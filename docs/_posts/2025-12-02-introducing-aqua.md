---
layout: default
title: "Introducing Aqua: Coordinate Multiple AI Agents on Your Codebase"
date: 2025-12-02
---

# Introducing Aqua: Coordinate Multiple AI Agents on Your Codebase

Today I'm releasing **Aqua** (Autonomous QUorum of Agents), a lightweight CLI tool for coordinating multiple AI coding agents working on the same codebase.

![Aqua in action]({{ site.baseurl }}/assets/images/aqua-demo.gif)

## The Problem

AI coding agents like Claude Code, Codex CLI, and Gemini CLI are powerful - but they're designed for single-agent use. When you want to parallelize work across multiple agents, things get messy:

- **Task conflicts**: Two agents might claim the same task
- **File conflicts**: Agents editing the same file creates merge nightmares
- **No visibility**: You can't see what each agent is doing
- **No communication**: Agents can't coordinate with each other

## The Solution

Aqua provides a shared coordination layer using a simple SQLite database. Each agent:

1. **Claims tasks** from a shared queue (with atomic locking)
2. **Locks files** before editing them
3. **Reports progress** visible to all agents and you
4. **Communicates** via messages to other agents

## How It Works

```bash
# Initialize Aqua in your project
cd my-project
aqua init
aqua setup --all  # Adds instructions to CLAUDE.md, AGENTS.md, GEMINI.md

# Add tasks with priorities and dependencies
aqua add "Set up FastAPI project" -p 9
aqua add "Create User model" -p 8 --after "Set up FastAPI project"
aqua add "Build /users endpoints" -p 7

# Spawn 3 AI agents in new terminals
aqua spawn 3

# Watch them work in real-time
aqua watch
```

Each spawned agent automatically:
1. Reads the coordination instructions from its MD file
2. Joins the quorum and reports for duty
3. Claims tasks respecting priorities and dependencies
4. Locks files before editing
5. Reports progress periodically
6. Marks tasks done and claims the next one

## Let the Agent Do It

You can also let the agent handle everything. Just run `aqua setup --all`, start your AI agent, and ask it to plan the project:

![Agent-driven workflow]({{ site.baseurl }}/assets/images/aqua-agent-demo.gif)

The agent reads CLAUDE.md, understands Aqua's capabilities, and handles task breakdown, spawning, and coordination autonomously.

## Key Features

### Task Dependencies

Tasks can depend on other tasks:

```bash
aqua add "Write tests" --after "Build API endpoints"
```

An agent won't claim "Write tests" until "Build API endpoints" is done.

### File Locking

Prevent edit conflicts:

```bash
aqua lock src/handlers.py   # Lock before editing
# ... do work ...
aqua unlock src/handlers.py # Release when done
```

### Blocking Messages

Agents can ask questions and wait for replies:

```bash
# Agent 1 asks a question
aqua ask "Should I use Redis or SQLite for caching?" --to @leader --timeout 60

# Leader replies
aqua reply 42 "Use SQLite, it's simpler for this use case"
```

### Live Monitoring

```bash
aqua watch   # Real-time dashboard with updates every 2s
aqua logs    # Tail event stream (like tail -f)
```

### JSON Mode for Automation

```bash
aqua status --json | jq .tasks
export AQUA_JSON=1  # All commands output JSON
```

## Architecture

Aqua uses SQLite with WAL mode for concurrent access. There's no server, no Docker, no Redis - just a single database file in `.aqua/aqua.db`.

```
your-project/
  .aqua/
    aqua.db           # SQLite database
    worker-1.session  # Agent session files
    worker-2.session
  CLAUDE.md           # Instructions for Claude Code
  AGENTS.md           # Instructions for Codex CLI
  GEMINI.md           # Instructions for Gemini CLI
```

## Install

```bash
pip install aqua-coord
```

Requires Python 3.10+.

## What's Next
I tried getting Cursor and other IDE agents to play nice with these CLI agents, but I couldn't successfully do it. This IME will be the biggest unlock, so that's what I'll be working on actively. 

I believe that as agents become smarter, they will discover ways to use aqua that even I didn't envision. However, I have some immediate plans for features that I think will enrich aqua:
- A role tag for each agent that is spawned so that the agent knows its responsibilities -- like a code review agent, or a frontend agent which will pick up tasks that it thinks it is best suited to work on.
- An interview/eval mode where a leader agent can interview/evaluate agents it spawns to ensure the tasks are being picked up by the most capable agent.
- A planning mode where multiple agents can come together and plan work - like a design review, or a sprint planning 😄
- Git merge conflict detection and resolution 
- Web dashboard for visual monitoring (not my highest priority)

### QOL improvements
If you've used or even seen the gifs where aqua is in action, you'd have noticed some rough edges and poor comprehension from agents that try to use aqua. These hinder effective utilization and at the same time might waste tokens. To that end, I will constantly be using and pushing bug fixes and QOL improvements. Please update as often as you can! 

## Links

- **GitHub**: [github.com/vignesh07/aqua](https://github.com/vignesh07/aqua)
- **PyPI**: [pypi.org/project/aqua-coord](https://pypi.org/project/aqua-coord/)
- **Docs**: [vignesh07.github.io/aqua](https://vignesh07.github.io/aqua)

---

Aqua is open source under the MIT license.
