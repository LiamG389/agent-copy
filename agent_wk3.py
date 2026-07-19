"""
Calendar Agent — main file.

This is where the REAL version of the agent lives, as opposed to the
Colab notebooks, which are scratch space for testing one piece at a
time. As each notebook cell starts working, copy it into the matching
section below.

Section map:
  SETUP              <- Week 1/2 notebook (client + model setup)
  MOCK CALENDAR       <- fake data store, swap for the real Google
                          Calendar API once the agent logic works
  SYSTEM PROMPT       <- Week 2 notebook
  TOOLS               <- Week 3 notebook
  CONFIRMATION GATE    <- Week 3 notebook (the destructive-action check)
  AGENT LOOP          <- Week 3 notebook (ties everything together)
  MAIN                <- a simple command-line chat loop for testing
"""

import os
from google import genai
from google.genai import types

# ===== SETUP =====
API_KEY = "YOUR_API_KEY_HERE"
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-3.5-flash"


# ===== MOCK CALENDAR =====
# A plain list standing in for a real calendar. Swap this out for the
# Google Calendar API later without changing anything below it, since
# list_events/create_event/etc. are the only things that touch it.
MOCK_CALENDAR = [
    {"id": 1, "title": "Meeting", "start": "2026-07-21 15:00", "end": "2026-07-21 15:30"},
    {"id": 2, "title": "Dentist", "start": "2026-07-24 09:00", "end": "2026-07-24 10:00"},
]


# ===== SYSTEM PROMPT =====
SYSTEM_PROMPT = """
You are a calendar-management agent for one user. You have tools to
list, create, edit, and delete events on their calendar. Always call
list_events to check for conflicts before creating or editing an
event.

Decision rules:
- If a request is clear and non-destructive, call the right tool.
- If a request is ambiguous, ask a clarifying question instead of
  guessing — do not call a tool yet.
- Editing or deleting an existing event is destructive even if it
  doesn't look like it ("update" and "move" still overwrite the old
  value with no undo). Propose the change in plain language rather
  than assuming approval; the code will ask the user to confirm
  before it actually runs.
"""


# ===== TOOLS =====
# Plain Python functions. The docstring and type hints are what the
# model sees as the tool's description — keep both accurate, since
# they're the only documentation the model gets.

def list_events(start_date: str, end_date: str) -> list[dict]:
    """List calendar events between two dates.

    Args:
        start_date: Start of the range, as YYYY-MM-DD.
        end_date: End of the range, as YYYY-MM-DD.
    """
    return [e for e in MOCK_CALENDAR if start_date <= e["start"][:10] <= end_date]


def create_event(title: str, start: str, end: str) -> dict:
    """Create a new calendar event. Call list_events first to check for conflicts.

    Args:
        title: Event title.
        start: Start time, as "YYYY-MM-DD HH:MM".
        end: End time, as "YYYY-MM-DD HH:MM".
    """
    event = {"id": len(MOCK_CALENDAR) + 1, "title": title, "start": start, "end": end}
    MOCK_CALENDAR.append(event)
    return event


def edit_event(event_id: int, title: str = "", start: str = "", end: str = "") -> dict:
    """Overwrite fields on an existing event. Destructive: the code will confirm first.

    Args:
        event_id: The id of the event to change.
        title: New title, if changing it. Leave blank to keep the current value.
        start: New start time, if changing it. Leave blank to keep the current value.
        end: New end time, if changing it. Leave blank to keep the current value.
    """
    for e in MOCK_CALENDAR:
        if e["id"] == event_id:
            if title:
                e["title"] = title
            if start:
                e["start"] = start
            if end:
                e["end"] = end
            return e
    return {"error": f"No event with id {event_id}"}


def delete_event(event_id: int) -> dict:
    """Remove an event from the calendar. Destructive: the code will confirm first.

    Args:
        event_id: The id of the event to remove.
    """
    global MOCK_CALENDAR
    before = len(MOCK_CALENDAR)
    MOCK_CALENDAR = [e for e in MOCK_CALENDAR if e["id"] != event_id]
    if len(MOCK_CALENDAR) == before:
        return {"error": f"No event with id {event_id}"}
    return {"deleted": event_id}


TOOLS = [list_events, create_event, edit_event, delete_event]
TOOL_MAP = {t.__name__: t for t in TOOLS}

# The enforcement point from this week's lesson: this set is checked
# in code, not just described in the prompt, so it holds even if the
# model "forgets" the rule.
CONFIRM_REQUIRED = {"edit_event", "delete_event"}


# ===== CONFIRMATION GATE =====
def run_tool_call(call) -> dict:
    """Executes one model-requested tool call, gating destructive ones on user approval."""
    name = call.name
    args = dict(call.args) if call.args else {}

    if name in CONFIRM_REQUIRED:
        print(f"\n  The agent wants to call {name}({args})")
        allowed = input("  Allow this? [y/N] ").strip().lower() == "y"
        if not allowed:
            return {"cancelled": True, "reason": "user declined"}

    if name not in TOOL_MAP:
        return {"error": f"Unknown tool: {name}"}
    return TOOL_MAP[name](**args)


# ===== AGENT LOOP =====
def run_turn(history: list, user_input: str) -> tuple[str, list]:
    """Runs one full user turn: model call -> any tool calls -> final answer.

    `history` is the running conversation (list of types.Content) so the
    model keeps context across turns. Returns the agent's reply text and
    the updated history.
    """
    history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS,
        # Disabled on purpose: automatic function calling would run
        # delete_event the moment the model asks for it. Manual handling
        # is what makes the confirmation gate above possible.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    # Loop, not a single check: some requests need more than one tool call
    # in sequence (e.g. list_events to find a meeting, THEN create_event
    # once the details are known). Keep going until the model responds
    # with plain text instead of another function call.
    max_rounds = 5
    for _ in range(max_rounds):
        response = client.models.generate_content(model=MODEL, contents=history, config=config)
        history.append(response.candidates[0].content)

        if not response.function_calls:
            return response.text, history

        for call in response.function_calls:
            result = run_tool_call(call)
            history.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=call.name, response={"result": result})],
            ))

    return "Sorry, that took too many steps -- can you rephrase or simplify the request?", history


# ===== MAIN =====
if __name__ == "__main__":
    history = []
    print("Calendar agent ready. Type a request, or 'quit' to exit.")
    while True:
        user_input = input("\nYou: ")
        if user_input.strip().lower() == "quit":
            break
        answer, history = run_turn(history, user_input)
        print(f"\nAgent: {answer}")
