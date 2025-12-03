---
layout: default
title: Aqua - Autonomous QUorum of Agents
---

# Aqua

**Autonomous QUorum of Agents** - Lightweight coordinator for CLI AI agents.

[![PyPI version](https://badge.fury.io/py/aqua-coord.svg)](https://badge.fury.io/py/aqua-coord)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## What is Aqua?

Aqua enables multiple AI agents (Claude Code, Codex CLI, Gemini CLI) running in separate terminal sessions to collaborate on tasks within a shared codebase.

When working with AI coding agents, you often want multiple agents working in parallel on different tasks. But without coordination, agents can:
- Work on the same task simultaneously
- Edit the same files and create conflicts
- Lack visibility into what other agents are doing

Aqua solves this with:
- **Shared task queue** with atomic claiming
- **File locking** to prevent conflicts
- **Inter-agent messaging** for coordination
- **Live monitoring** to see all agent activity

## Quick Install

```bash
pip install aqua-coord
```

## Quick Start

```bash
# 1. Initialize in your project
cd your-project
aqua init
aqua setup --all  # Add instructions to CLAUDE.md, AGENTS.md, GEMINI.md

# 2. Add tasks
aqua add "Set up project structure" -p 9
aqua add "Implement data models" -p 8 --after "Set up project structure"
aqua add "Build API endpoints" -p 7

# 3. Spawn agents
aqua spawn 3

# 4. Monitor
aqua watch
```

## Features

| Feature | Description |
|---------|-------------|
| **Task Queue** | Priority-based task management with dependencies |
| **File Locking** | Prevent multiple agents from editing the same file |
| **Blocking Messages** | Ask questions and wait for replies from other agents |
| **Live Monitoring** | Real-time dashboard and event stream |
| **Leader Election** | Automatic coordination with one agent assuming leadership |
| **Crash Recovery** | Automatic detection of dead agents and task reassignment |
| **Agent Agnostic** | Works with Claude Code, Codex CLI, Gemini CLI, or any CLI tool |
| **Zero Dependencies** | Uses SQLite - no Redis, Docker, or external services |
| **JSON Mode** | Full `--json` support and `AQUA_JSON=1` env var |

## Supported Agent CLIs

| CLI | Instruction File | Default Model |
|-----|------------------|---------------|
| [Claude Code](https://claude.ai/code) | `CLAUDE.md` | sonnet |
| [Codex CLI](https://github.com/openai/codex-cli) | `AGENTS.md` | o4-mini |
| [Gemini CLI](https://github.com/google/gemini-cli) | `GEMINI.md` | gemini-2.5-pro |

## Links

- [GitHub Repository](https://github.com/vignesh07/aqua)
- [PyPI Package](https://pypi.org/project/aqua-coord/)
- [Full Documentation](https://github.com/vignesh07/aqua#readme)

---

Made for the multi-agent future.
