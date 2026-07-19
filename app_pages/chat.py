"""
Chat page -- talk to the calendar agent.

Note: st.set_page_config and the page title are handled in dashboard.py
(the app entry point), not here -- Streamlit only allows one of each
per app run.
"""

import streamlit as st
from google.genai import types

from agent_wk4 import client, MODEL, get_system_prompt, TOOLS, TOOL_MAP, CONFIRM_REQUIRED


def make_config():
    return types.GenerateContentConfig(
        system_instruction=get_system_prompt(),
        tools=TOOLS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def advance(max_rounds: int = 5) -> None:
    """Runs model rounds against st.session_state.history until one of:
    - a final text answer (appended to history, then we return)
    - a destructive tool call needs approval (stored in pending_call, we
      return so the UI can render Approve/Decline before continuing)
    - the round cap is hit (a fallback message is appended)
    """
    config = make_config()
    for _ in range(max_rounds):
        response = client.models.generate_content(
            model=MODEL, contents=st.session_state.history, config=config
        )
        st.session_state.history.append(response.candidates[0].content)

        if not response.function_calls:
            return

        for call in response.function_calls:
            if call.name in CONFIRM_REQUIRED:
                st.session_state.pending_call = call
                return

            result = TOOL_MAP[call.name](**dict(call.args or {}))
            st.session_state.history.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=call.name, response={"result": result})],
            ))

    st.session_state.history.append(types.Content(
        role="model",
        parts=[types.Part.from_text(
            text="Sorry, that took too many steps -- can you rephrase or simplify the request?"
        )],
    ))


# ----- session state -----
if "history" not in st.session_state:
    st.session_state.history = []
if "pending_call" not in st.session_state:
    st.session_state.pending_call = None

if st.button("Clear conversation", icon=":material/refresh:"):
    st.session_state.history = []
    st.session_state.pending_call = None
    st.rerun()

# ----- replay the conversation so far -----
for content in st.session_state.history:
    text = content.parts[0].text if content.parts else None
    if not text:
        continue  # skip function-call / function-response parts, text only
    role = "user" if content.role == "user" else "assistant"
    with st.chat_message(role):
        st.write(text)

# ----- either show the confirmation gate, or the normal chat box -----
if st.session_state.pending_call:
    call = st.session_state.pending_call
    st.warning(f"The agent wants to run **{call.name}**({dict(call.args or {})})")
    col1, col2 = st.columns(2)
    approved = col1.button("Approve", icon=":material/check:", width="stretch")
    declined = col2.button("Decline", icon=":material/close:", width="stretch")

    if approved or declined:
        result = (
            TOOL_MAP[call.name](**dict(call.args or {}))
            if approved
            else {"cancelled": True, "reason": "user declined"}
        )
        st.session_state.history.append(types.Content(
            role="user",
            parts=[types.Part.from_function_response(name=call.name, response={"result": result})],
        ))
        st.session_state.pending_call = None
        with st.spinner("Thinking..."):
            advance()
        st.rerun()
else:
    user_input = st.chat_input("Ask your calendar agent something...")
    if user_input:
        st.session_state.history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
        )
        with st.spinner("Thinking..."):
            advance()
        st.rerun()