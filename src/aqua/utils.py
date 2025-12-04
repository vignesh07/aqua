"""Utility functions for Aqua."""

import os
import random
import uuid
from datetime import datetime, timezone

# Adjectives and nouns for generating memorable agent names
ADJECTIVES = [
    "brave", "calm", "dark", "eager", "fair", "gentle", "happy", "idle",
    "jolly", "keen", "lively", "merry", "noble", "odd", "proud", "quick",
    "rapid", "silent", "tall", "unique", "vivid", "warm", "young", "zesty",
    "amber", "blue", "coral", "dusty", "emerald", "frosty", "golden", "hazy",
]

NOUNS = [
    "falcon", "tiger", "eagle", "wolf", "bear", "lion", "hawk", "fox",
    "otter", "raven", "shark", "whale", "cobra", "crane", "drake", "elk",
    "finch", "gecko", "heron", "ibis", "jay", "koala", "lemur", "moose",
    "newt", "owl", "panda", "quail", "robin", "swan", "trout", "viper",
]


def generate_short_id() -> str:
    """Generate a short unique ID (8 characters)."""
    return uuid.uuid4().hex[:8]


def generate_agent_name() -> str:
    """Generate a memorable agent name like 'brave-falcon'."""
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f"{adjective}-{noun}"


def process_exists(pid: int) -> bool:
    """Check if a process exists without killing it."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_current_pid() -> int:
    """Get the current process ID."""
    return os.getpid()


def utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime.

    This is the recommended replacement for datetime.utcnow() which is
    deprecated in Python 3.12+.
    """
    return datetime.now(timezone.utc)


def now_iso() -> str:
    """Get current UTC time as ISO8601 string."""
    return utc_now().isoformat()


def parse_iso(iso_string: str) -> datetime:
    """Parse ISO8601 string to datetime.

    Note: Returns timezone-naive datetime for compatibility with existing
    database storage. Internal comparisons should handle this.
    """
    return datetime.fromisoformat(iso_string)


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as 'X ago' relative to now."""
    # Handle both timezone-aware and naive datetimes
    now = utc_now()
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        now = now.replace(tzinfo=None)
    delta = now - dt

    seconds = int(delta.total_seconds())

    if seconds < 0:
        return "in the future"
    elif seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}m ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours}h ago"
    else:
        days = seconds // 86400
        return f"{days}d ago"


def truncate(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def parse_tags(tags_str: str | None) -> list:
    """Parse comma-separated tags string into list."""
    if not tags_str:
        return []
    return [t.strip() for t in tags_str.split(",") if t.strip()]
