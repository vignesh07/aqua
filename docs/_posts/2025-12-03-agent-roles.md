---
layout: default
title: "Agent Roles: Spawn Specialized Teams That Self-Organize"
date: 2025-12-03
---

# Agent Roles: Spawn Specialized Teams That Self-Organize

In the [introductory post]({{ site.baseurl }}{% post_url 2025-12-02-introducing-aqua %}), I mentioned wanting to add role-based task assignment so agents know their responsibilities. Today, that feature is live.

## The Problem with Generalist Agents

When you spawn multiple agents, they all compete for the same tasks. The first agent to run `aqua claim` gets the next task, regardless of whether they're the best fit. This leads to:

- **Suboptimal assignment**: Your best frontend agent might end up writing backend code
- **Context switching**: Agents waste time ramping up on unfamiliar domains
- **No specialization**: You can't leverage the strengths of different agent configurations

## The Solution: Agent Roles

Now you can spawn agents with roles that guide their task selection:

```bash
# Spawn a specialized team
aqua spawn 4 --roles frontend,backend,testing,reviewer
```

Each agent joins with its assigned role and **prioritizes tasks that match**. A `frontend` agent will claim tasks tagged `frontend` before touching anything else.

## How It Works

### 1. Tag Your Tasks

When adding tasks, use tags that match roles:

```bash
aqua add "Fix navbar responsiveness" -t frontend -p 7
aqua add "Add /products endpoint" -t backend -p 7
aqua add "Write integration tests" -t testing -p 6
aqua add "Review authentication PR" -t review -p 8
```

### 2. Spawn with Roles

```bash
# Option 1: Explicit role list
aqua spawn 4 --roles frontend,backend,testing,reviewer

# Option 2: Auto-assign predefined roles
aqua spawn 4 --assign-roles
# Cycles through: reviewer, frontend, backend, testing, devops

# Option 3: Same role for all agents
aqua spawn 3 --role reviewer  # All three become reviewers
```

### 3. Agents Self-Organize

When an agent runs `aqua claim`:

1. **First**, it looks for pending tasks tagged with its role
2. **If found**, it claims the highest-priority matching task
3. **If not**, it can claim any available task (and is informed of the mismatch)

The output from `aqua refresh` now shows the agent's role:

```
╭─────────────────────────────────────╮
│ You are: worker-1 (frontend) ★ LEADER │
╰─────────────────────────────────────╯
```

## Predefined Roles

These roles come with built-in tag matching:

| Role | Matches tags |
|------|-------------|
| `reviewer` | review, pr, code-review |
| `frontend` | frontend, ui, css, react, component |
| `backend` | backend, api, database, server |
| `testing` | test, testing, qa, e2e |
| `devops` | devops, deploy, ci, infra |

## Custom Roles

Any string works as a role. Agents with custom roles match tasks with that exact tag:

```bash
aqua spawn 2 --roles security,performance

aqua add "Audit auth module for vulnerabilities" -t security
aqua add "Profile and optimize hot paths" -t performance
```

## Completely Optional

Roles are a power-user feature. If you don't use them, nothing changes:

```bash
# This still works exactly as before
aqua spawn 3
aqua add "Some task"
```

Agents without roles claim any available task, in priority order.

## Example: Full Workflow

```bash
# 1. Initialize
aqua init
aqua setup --all

# 2. Add role-tagged tasks
aqua add "Review PR #42 for security issues" -t review -p 9
aqua add "Fix mobile nav menu" -t frontend -p 7
aqua add "Add user preferences API" -t backend -p 7
aqua add "Write e2e tests for checkout" -t testing -p 6

# 3. Spawn specialized team
aqua spawn 4 --assign-roles -b

# 4. Watch them work
aqua watch
```

Each agent claims tasks matching their specialty. The reviewer grabs PR #42, the frontend agent fixes the nav menu, and so on.

## Under the Hood

The implementation is straightforward:

1. **`spawn` passes role via environment variable** (`AQUA_AGENT_ROLE`)
2. **`join` reads the env var** and stores role in the agent record
3. **`claim` queries tasks matching the role first**, falling back to any task
4. **Role is visible** in `refresh` output and JSON responses

The role-matching query is simple: tasks where `tags LIKE '%"role"%'`. SQLite handles it efficiently.

## What's Next

With roles working, the next feature on my list is the **interview/eval mode** - where a leader agent can evaluate spawned agents before assigning them tasks. This would enable more sophisticated team composition based on actual agent capabilities rather than just role labels.

## Install / Upgrade

```bash
pip install --upgrade aqua-coord
```

---

Roles make multi-agent coordination feel more like managing a real team. Each agent knows their specialty and self-selects appropriate work.

---

**Previous:** [Introducing Aqua]({{ site.baseurl }}{% post_url 2025-12-02-introducing-aqua %}) | **Next:** [Serialize: Solving the Context Window Problem]({{ site.baseurl }}{% post_url 2025-12-04-serialize-long-running-projects %}) | [All Posts]({{ site.baseurl }}/blog)
