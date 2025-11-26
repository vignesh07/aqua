# Aqua TODO - Based on v0.1 Testing Feedback

## High Priority (Blocking Issues)

### 1. Fix agent ID persistence after `aqua join`
**Problem**: `aqua join` prints the agent ID but doesn't persist it. User has to manually `export AQUA_AGENT_ID=xxx` for every command.

**Solution**:
- Already have session-based files in `.aqua/sessions/` but it's not working
- Debug why `store_agent_id()` isn't being called or isn't working after join
- Ensure `aqua refresh` finds the ID immediately after `aqua join`

**Files**: `src/aqua/cli.py` - `join` command, `store_agent_id()`, `get_stored_agent_id()`

---

### 2. Fix `aqua spawn` - AppleScript syntax error
**Problem**: `aqua spawn` fails with "Expected end of line" - quote escaping issues in osascript.

**Solution**:
- Test and fix the AppleScript string escaping
- Add fallback for non-macOS (Linux: gnome-terminal, xterm, etc.)
- Add `--dry-run` to show the command without executing

**Files**: `src/aqua/cli.py` - `spawn` command

---

## Medium Priority (Important Features)

### 3. Task dependencies
**Problem**: Can't express "task B depends on task A completing first"

**Solution**:
```bash
aqua add "Build API" --depends-on <task_id>
aqua add "Write tests" --after "Build API"  # by title match
```
- Add `depends_on` column to tasks table
- `claim` skips tasks whose dependencies aren't done
- `aqua show` displays dependency chain

**Files**: `src/aqua/db.py`, `src/aqua/models.py`, `src/aqua/coordinator.py`, `src/aqua/cli.py`

---

### 4. File locking/claiming
**Problem**: No way to declare "I'm editing this file, don't touch it"

**Solution**:
```bash
aqua lock src/handlers.py          # Claim a file
aqua unlock src/handlers.py        # Release it
aqua locks                         # Show who has what locked
```
- New `file_locks` table: (file_path, agent_id, locked_at)
- `aqua status` shows locked files
- Instructions tell agents to check locks before editing

**Files**: New table in `db.py`, new commands in `cli.py`

---

### 5. Monitoring subagents from parent
**Problem**: No visibility into spawned agents' progress until they finish.

**Solution**:
```bash
aqua watch --json              # Machine-readable stream
aqua logs                      # Tail all agent activity
aqua logs --agent worker-1     # Specific agent's activity
```
- Use the existing `events` table for activity log
- Add more granular events (file edits, progress updates)

**Files**: `src/aqua/cli.py` - enhance `watch`, add `logs` command

---

## Lower Priority (Nice to Have)

### 6. Blocking agent-to-agent messages
**Problem**: `aqua msg` is fire-and-forget; can't ask and wait for response.

**Solution**:
```bash
aqua ask "Should I use Redis or SQLite?" --to worker-2 --wait
# Blocks until worker-2 responds with:
aqua reply <msg_id> "Use SQLite"
```
- Adds `reply_to` field to messages
- `--wait` polls for response with timeout

---

### 7. Headless/JSON mode for AI agents
**Problem**: Pretty terminal output is hard for AI agents to parse.

**Solution**:
- Already have `--json` on most commands
- Add `AQUA_JSON=1` env var to make JSON the default
- Ensure ALL commands support `--json` consistently

---

### 8. Background agent spawning worked via Claude's Task tool
**Note**: This actually worked! Claude spawned background agents using its own Task tool.
Consider documenting this as the recommended approach for Claude specifically.

---

## Summary

| Priority | Issue | Effort |
|----------|-------|--------|
| HIGH | Agent ID not persisting after join | Small |
| HIGH | `aqua spawn` AppleScript broken | Medium |
| MED | Task dependencies | Medium |
| MED | File locking | Medium |
| MED | Subagent monitoring/logs | Small |
| LOW | Blocking messages | Medium |
| LOW | Global JSON mode | Small |
