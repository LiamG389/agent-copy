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
  SYSTEM PROMPT       <- Week 2 notebook, extended in Week 4 with
                          memory.py's stored preferences
  TOOLS               <- Week 3 notebook, plus remember_preference
                          from Week 4
  CONFIRMATION GATE    <- Week 3 notebook (the destructive-action check)
  AGENT LOOP          <- Week 3 notebook (ties everything together)
  MAIN                <- a simple command-line chat loop for testing

Memory itself lives in memory_store.py, not here — see that file for
why it's split out.
"""

import os
from google import genai
from google.genai import types
from datetime import date
from memory_store import load_memory, remember_preference

# ===== SETUP =====
API_KEY = "YOUR_API_KEY_HERE"
client = genai.Client(api_key=API_KEY)
MODEL = "gemini-3.1-flash-lite"


# ===== MOCK CALENDAR =====
MOCK_CALENDAR = [
    {"id": 1, "title": "Meeting", "start": "2026-07-21 15:00", "end": "2026-07-21 15:30"},
    {"id": 2, "title": "Dentist", "start": "2026-07-24 09:00", "end": "2026-07-24 10:00"},
]
datenow = date.today()

# ===== SYSTEM PROMPT =====
SYSTEM_PROMPT_BASE = f"""
You are a calendar-management agent for one user. You have tools to
list, create, edit, and delete events on their calendar. Always call
list_events to check for conflicts before creating or editing an
event. It is currently {datenow}.

Decision rules:
- If a request is clear and non-destructive, call the right tool.
- If a request is ambiguous, ask a clarifying question instead of
  guessing — do not call a tool yet.
- Editing or deleting an existing event is destructive even if it
  doesn't look like it ("update" and "move" still overwrite the old
  value with no undo). Propose the change in plain language rather
  than assuming approval; the code will ask the user to confirm
  before it actually runs. On the other hand, creating an event is non-destructive.
  No verbal confirmation is needed before doing so. 
- If the user states a lasting preference (not a one-off request —
  e.g. "I never want meetings before 9am"), call remember_preference
  to save it. Do not call it for one-time requests like "move my 2pm."
"""


def get_system_prompt() -> str:
    """Builds the full system prompt: static rules + whatever's been remembered."""
    preferences = load_memory()
    if preferences:
        prefs_block = "\n".join(f"- {p}" for p in preferences)
    else:
        prefs_block = "(none saved yet)"
    return f"{SYSTEM_PROMPT_BASE}\nKnown preferences for this user (honor these without being asked again):\n{prefs_block}\n"


# ===== TOOLS =====
def list_events(start_date: str, end_date: str) -> list[dict]:
    """List calendar events between two dates. Dates are in the format YYYY-MM-DD"""
    print(f"    🔹 [Executing Tool] list_events(start_date='{start_date}', end_date='{end_date}')")
    events = [e for e in MOCK_CALENDAR if start_date <= e["start"][:10] <= end_date]
    print(f"    🔹 [Tool Result] Found {len(events)} event(s)")
    return events


def create_event(title: str, start: str, end: str) -> dict:
    """Create a new calendar event. Call list_events first to check for conflicts. """
    print(f"    🔹 [Executing Tool] create_event(title='{title}', start='{start}', end='{end}')")
    event = {"id": len(MOCK_CALENDAR) + 1, "title": title, "start": start, "end": end}
    MOCK_CALENDAR.append(event)
    print(f"    🔹 [Tool Result] Successfully created event ID {event['id']}")
    return event


def edit_event(event_id: int, title: str = "", start: str = "", end: str = "") -> dict:
    """Overwrite fields on an existing event. Destructive: the code will confirm first."""
    print(f"    🔹 [Executing Tool] edit_event(event_id={event_id}, title='{title}', start='{start}', end='{end}')")
    for e in MOCK_CALENDAR:
        if e["id"] == event_id:
            if title: e["title"] = title
            if start: e["start"] = start
            if end: e["end"] = end
            print(f"    🔹 [Tool Result] Successfully updated event ID {event_id}")
            return e
    print(f"    🔹 [Tool Error] No event found with ID {event_id}")
    return {"error": f"No event with id {event_id}"}


def delete_event(event_id: int) -> dict:
    """Remove an event from the calendar. Destructive: the code will confirm first."""
    print(f"    🔹 [Executing Tool] delete_event(event_id={event_id})")
    global MOCK_CALENDAR
    before = len(MOCK_CALENDAR)
    MOCK_CALENDAR = [e for e in MOCK_CALENDAR if e["id"] != event_id]
    if len(MOCK_CALENDAR) == before:
        print(f"    🔹 [Tool Error] No event found to delete with ID {event_id}")
        return {"error": f"No event with id {event_id}"}
    print(f"    🔹 [Tool Result] Successfully deleted event ID {event_id}")
    return {"deleted": event_id}


TOOLS = [list_events, create_event, edit_event, delete_event, remember_preference]
TOOL_MAP = {t.__name__: t for t in TOOLS}
CONFIRM_REQUIRED = {"edit_event", "delete_event"}


# ===== CONFIRMATION GATE =====
def run_tool_call(call) -> dict:
    """Executes one model-requested tool call, gating destructive ones on user approval."""
    name = call.name
    args = dict(call.args) if call.args else {}

    if name in CONFIRM_REQUIRED:
        print(f"\n⚠️  [Confirmation Gate Triggered] The agent wants to run a destructive action: {name}({args})")
        allowed = input("   Allow this? [y/N] ").strip().lower() == "y"
        if not allowed:
            print("❌ [Confirmation Gate] Action declined by user.")
            return {"cancelled": True, "reason": "user declined"}
        print("✅ [Confirmation Gate] Action approved by user.")

    if name not in TOOL_MAP:
        print(f"❌ [Error] Model tried to call an invalid tool: {name}")
        return {"error": f"Unknown tool: {name}"}
        
    return TOOL_MAP[name](**args)


# ===== AGENT LOOP =====
def run_turn(history: list, user_input: str) -> tuple[str, list]:
    """Runs one full user turn: model call -> any tool calls -> final answer."""
    history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))

    print("🔹 [Agent Setup] Rebuilding prompt context with latest memories...")
    config = types.GenerateContentConfig(
        system_instruction=get_system_prompt(),
        tools=TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    max_rounds = 5
    for round_num in range(1, max_rounds + 1):
        print(f"🔹 [LLM Request] Thinking... (Round {round_num}/{max_rounds})")
        response = client.models.generate_content(model=MODEL, contents=history, config=config)
        history.append(response.candidates[0].content)

        # Case 1: Model responded with a normal chat answer
        if not response.function_calls:
            print("🔹 [LLM Response] Model generated text answer.")
            return response.text, history

        # Case 2: Model wants to execute one or more tools
        print(f"🔹 [LLM Response] Model requested tool call(s): {[c.name for c in response.function_calls]}")
        for call in response.function_calls:
            result = run_tool_call(call)
            
            # Feed the tool results back into the history so the LLM can process them in the next loop
            history.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=call.name, response={"result": result})],
            ))

    print("❌ [Agent Loop] Maximum internal rounds reached without a final text response.")
    return "Sorry, that took too many steps -- can you rephrase or simplify the request?", history


# ===== MAIN =====
if __name__ == "__main__":
    history = []
    print("Calendar agent ready. Type a request, or 'quit' to exit.")
    while True:
        user_input = input("\nYou: ")
        if user_input.strip().lower() == "quit":
            print("Goodbye!")
            break
        answer, history = run_turn(history, user_input)
        print(f"\nAgent: {answer}")