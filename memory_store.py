"""
Persisted user memory for the calendar agent.

Kept in its own file on purpose: everything in agent.py so far only
needs to survive within one running session (it lives in `history`,
which resets the moment the program stops). Memory's entire job is
surviving *past* that restart, so it needs a home outside the running
program — a plain JSON file, here.
"""

import json
import os

MEMORY_FILE = "memory.json"


def load_memory() -> list[str]:
    """Load stored preference strings from disk. Returns [] if none saved yet."""
    if not os.path.exists(MEMORY_FILE):
        return []
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(preferences: list[str]) -> None:
    """Overwrite the memory file with the given list of preference strings."""
    with open(MEMORY_FILE, "w") as f:
        json.dump(preferences, f, indent=2)


def remember_preference(preference: str) -> dict:
    """Save a lasting user preference so it's honored in future sessions too.

    Only call this for things that should apply going forward, not for
    one-off requests. E.g. call it for "I never want meetings before
    9am" -- do NOT call it for "move my 2pm to 3pm" (that's a one-time
    edit_event, not a standing preference).

    Args:
        preference: A plain-language preference to remember, e.g.
            "never book meetings before 9am".
    """
    preferences = load_memory()
    if preference not in preferences:
        preferences.append(preference)
        save_memory(preferences)
    return {"remembered": preference, "all_preferences": preferences}
