"""Atomic Habits Coach — Streamlit app for Friday book sharing."""

from __future__ import annotations

import json
import os
import re
from html import escape

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from pdf_report import build_pdf
from habit_prompts import SYSTEM_PROMPT, build_chat_system_prompt, build_user_prompt
from users_store import (
    delete_user,
    get_user,
    load_users,
    upsert_user,
    user_label,
)


def user_display_role(user: dict) -> str:
    """Role text for UI captions (kept in app.py to avoid stale Streamlit imports)."""
    role = (user.get("role") or "").strip()
    return role if role else "Linktal teammate"

load_dotenv()

HABIT_SUGGESTIONS = [
    "Read more books",
    "Exercise / work out",
    "Drink more water",
    "Meditate or journal",
    "Stop scrolling in bed",
    "Sleep earlier",
    "Eat healthier",
]

ANCHORS = [
    "Drink morning coffee / tea",
    "Commute / arrive at work",
    "Sit at my desk",
    "Brush my teeth",
    "Finish lunch",
    "Put my phone on charge",
]

OBSTACLES = [
    "Lack of time",
    "Forgetfulness",
    "Too tired",
    "No motivation",
    "Environment distractions",
]


def _sync_multi_to_text(choice_key: str, text_key: str) -> None:
    """Write multi-select choices into the editable text box below."""
    selected = st.session_state.get(choice_key) or []
    st.session_state[text_key] = ", ".join(selected)


def combine_for_ai(selected: list[str], free_text: str) -> str:
    """Merge multi-select + free text so both are fed to the model."""
    picks = [s.strip() for s in (selected or []) if s and str(s).strip()]
    notes = (free_text or "").strip()
    joined = ", ".join(picks)

    if picks and notes:
        if notes == joined:
            return joined
        # Avoid duplicating if notes already starts with the joined picks
        if notes.startswith(joined):
            return notes
        return f"Selections: {joined}. Extra notes: {notes}"
    if notes:
        return notes
    return joined


def _ensure_field_defaults() -> None:
    # Reset legacy single-select string values to multi-select lists
    for key in ("goal_choice", "anchor_choice", "obstacle_choice"):
        if key not in st.session_state or not isinstance(st.session_state[key], list):
            st.session_state[key] = []
    for key in ("goal_text", "anchor_text", "obstacle_text"):
        if key not in st.session_state or not isinstance(st.session_state[key], str):
            st.session_state[key] = ""


LINKTAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --ah-purple: #7c3aed;
  --ah-purple-dark: #6d28d9;
  --ah-purple-soft: #f3e8ff;
  --ah-border: #e5e7eb;
  --ah-text: #111827;
  --ah-muted: #6b7280;
  --ah-label: #6b7280;
  --ah-bg: #f9fafb;
  --ah-sidebar: #ffffff;
  --ah-radius: 8px;
}

html, body, [class*="css"], .stApp {
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}

.stApp {
  background: var(--ah-bg) !important;
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] {
  background: transparent !important;
}
div[data-testid="stDecoration"] { display: none; }
div[data-testid="stToolbar"] { right: 0.5rem; }

section[data-testid="stSidebar"] {
  background: var(--ah-sidebar) !important;
  border-right: 1px solid var(--ah-border);
}
div[data-testid="stSidebarNav"] { display: none; }

.block-container {
  max-width: 720px !important;
  padding-top: 1.25rem !important;
  padding-bottom: 2.5rem !important;
  padding-left: 1.25rem !important;
  padding-right: 1.25rem !important;
}

.brand-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: #1e3a5f;
  letter-spacing: -0.02em;
  margin: 0 0 0.2rem 0;
}
.brand-sub {
  font-size: 0.7rem;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 1rem;
}
.nav-item {
  display: block;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  color: #374151;
  font-size: 0.9rem;
  font-weight: 500;
}
.nav-item.active {
  background: var(--ah-purple-soft);
  color: var(--ah-purple);
  border-left: 3px solid var(--ah-purple);
  padding-left: calc(0.85rem - 3px);
}
.nav-item .sub {
  display: block;
  font-size: 0.72rem;
  font-weight: 400;
  color: #9ca3af;
  margin-top: 0.15rem;
}
.nav-item.active .sub { color: #a78bfa; }

.page-title {
  font-size: clamp(1.45rem, 4vw, 1.75rem);
  font-weight: 700;
  color: var(--ah-text);
  letter-spacing: -0.02em;
  margin: 0 0 0.3rem 0;
  line-height: 1.25;
}
.page-pitch {
  color: var(--ah-muted);
  font-size: 0.95rem;
  margin: 0 0 1.1rem 0;
  line-height: 1.45;
}
.step-hint {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: var(--ah-purple-soft);
  color: var(--ah-purple);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  margin-bottom: 0.75rem;
}
.q-block {
  margin-bottom: 0.15rem;
}
.q-hint {
  font-size: 0.78rem;
  color: #9ca3af;
  margin: -0.15rem 0 0.35rem 0;
}

.card {
  background: #ffffff;
  border: 1px solid var(--ah-border);
  border-radius: var(--ah-radius);
  padding: 1.15rem 1.25rem;
  margin-bottom: 0.75rem;
}
.law-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ah-purple);
  margin-bottom: 0.3rem;
}
.law-law {
  font-size: 0.75rem;
  color: #9ca3af;
  margin-bottom: 0.45rem;
}
.law-body {
  font-size: 0.92rem;
  color: var(--ah-text);
  font-weight: 500;
  line-height: 1.45;
  margin: 0;
}
.success-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #16a34a;
  font-weight: 600;
  font-size: 0.92rem;
  margin: 0.75rem 0 0.85rem 0;
  padding: 0.65rem 0.9rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: var(--ah-radius);
}
.stack-highlight {
  background: #faf5ff;
  border: 1px solid #e9d5ff;
  border-radius: var(--ah-radius);
  padding: 1rem 1.15rem;
  margin: 0 0 0.75rem 0;
  font-size: 1.02rem;
  font-weight: 600;
  color: var(--ah-text);
  line-height: 1.4;
}
.stack-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--ah-purple);
  letter-spacing: 0.05em;
  margin-bottom: 0.35rem;
}

/* Bordered question card */
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: #ffffff !important;
  border: 1px solid var(--ah-border) !important;
  border-radius: 8px !important;
  padding: 0.35rem 0.5rem 0.6rem 0.5rem !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] input,
div[data-testid="stVerticalBlockBorderWrapper"] textarea,
div[data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="select"] > div {
  min-height: 44px !important;
  background-color: #ffffff !important;
  color: var(--ah-text) !important;
  border: 1px solid #d1d5db !important;
  border-radius: 8px !important;
  font-size: 0.95rem !important;
  box-shadow: none !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] textarea {
  min-height: 72px !important;
  line-height: 1.4 !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] input:focus,
div[data-testid="stVerticalBlockBorderWrapper"] textarea:focus,
div[data-testid="stVerticalBlockBorderWrapper"] [data-baseweb="select"] > div:focus-within {
  border-color: var(--ah-purple) !important;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15) !important;
}

.q-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #111827;
  margin: 0.85rem 0 0.4rem 0;
}
.q-title:first-child { margin-top: 0.25rem; }
.chat-wrap {
  margin-top: 0.5rem;
}
div[data-testid="stChatMessage"] {
  background: #ffffff !important;
  border: 1px solid var(--ah-border) !important;
  border-radius: 8px !important;
  padding: 0.5rem 0.65rem !important;
  margin-bottom: 0.5rem !important;
}
div[data-testid="stChatMessage"] p,
div[data-testid="stChatMessage"] span,
div[data-testid="stChatMessage"] li,
div[data-testid="stChatMessage"] div,
div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] * {
  color: #111827 !important;
}
div[data-testid="stChatMessage"] strong,
div[data-testid="stChatMessage"] b {
  color: #111827 !important;
  font-weight: 700 !important;
}
/* Chat input — readable on light UI */
[data-testid="stChatInput"] {
  background: #f9fafb !important;
  border-top: 1px solid var(--ah-border) !important;
}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input {
  color: #111827 !important;
  background: #ffffff !important;
  caret-color: #111827 !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: #9ca3af !important;
}

.pdf-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #6b7280;
  font-size: 0.9rem;
  margin: 0.35rem 0 0.75rem 0;
}

.stButton > button,
.stDownloadButton > button,
div[data-testid="stForm"] button,
button[kind="primary"],
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
  background-color: var(--ah-purple) !important;
  background-image: none !important;
  color: #ffffff !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-size: 0.95rem !important;
  min-height: 44px !important;
  padding: 0.55rem 1.25rem !important;
  width: 100% !important;
  box-shadow: none !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
div[data-testid="stForm"] button:hover,
button[kind="primary"]:hover {
  background-color: var(--ah-purple-dark) !important;
  color: #ffffff !important;
  border: none !important;
}

@media (max-width: 768px) {
  .block-container {
    max-width: 100% !important;
    padding-top: 0.75rem !important;
    padding-left: 0.85rem !important;
    padding-right: 0.85rem !important;
    padding-bottom: 2rem !important;
  }
  div[data-testid="stForm"] {
    padding: 1rem 0.95rem 0.9rem 0.95rem !important;
  }
  .page-title { font-size: 1.4rem; }
  .page-pitch { font-size: 0.9rem; }
  .card { padding: 1rem; }
  div[data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
  }
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    min-width: 100% !important;
    flex: 1 1 100% !important;
  }
}

@media (min-width: 769px) {
  .block-container {
    max-width: 760px !important;
  }
}
</style>
"""


OPENROUTER_BASE = "https://openrouter.ai/api/v1"
MODEL_OPENAI = "gpt-4o-mini"
MODEL_OPENROUTER = "openai/gpt-4o-mini"


def _secret(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value.strip() or None
    try:
        return str(st.secrets[name]).strip() or None
    except Exception:
        return None


def _is_openrouter_key(api_key: str) -> bool:
    return api_key.startswith("sk-or-")


def make_client(api_key: str) -> OpenAI:
    base_url = os.getenv("OPENAI_BASE_URL")
    if not base_url and _is_openrouter_key(api_key):
        base_url = OPENROUTER_BASE
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def resolve_model(api_key: str) -> str:
    if _is_openrouter_key(api_key) or (
        os.getenv("OPENAI_BASE_URL") or ""
    ).startswith("https://openrouter.ai"):
        return MODEL_OPENROUTER
    return MODEL_OPENAI


def api_keys_in_order() -> list[str]:
    keys: list[str] = []
    for name in ("OPENAI_API_KEY", "OPENAI_API_KEY_FALLBACK"):
        key = _secret(name)
        if key and key not in keys:
            keys.append(key)
    return keys


def parse_plan_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _call_model(
    api_key: str,
    goal: str,
    anchor: str,
    obstacle: str,
    profile: dict | None = None,
) -> dict:
    client = make_client(api_key)
    response = client.chat.completions.create(
        model=resolve_model(api_key),
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(goal, anchor, obstacle, profile),
            },
        ],
    )
    content = response.choices[0].message.content or "{}"
    return parse_plan_json(content)


def generate_plan(
    goal: str,
    anchor: str,
    obstacle: str,
    profile: dict | None = None,
) -> dict:
    keys = api_keys_in_order()
    if not keys:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env or Streamlit secrets."
        )
    errors: list[str] = []
    for i, key in enumerate(keys):
        try:
            return _call_model(key, goal, anchor, obstacle, profile)
        except Exception as exc:  # noqa: BLE001 — try next key
            label = "primary" if i == 0 else "fallback"
            errors.append(f"{label}: {exc}")
            continue
    raise RuntimeError(
        "All API keys failed. " + " | ".join(errors)
    )


def _call_chat(
    api_key: str,
    system_prompt: str,
    history: list[dict[str, str]],
) -> str:
    client = make_client(api_key)
    messages = [{"role": "system", "content": system_prompt}, *history]
    response = client.chat.completions.create(
        model=resolve_model(api_key),
        temperature=0.7,
        messages=messages,
    )
    return (response.choices[0].message.content or "").strip()


def chat_reply(
    goal: str,
    anchor: str,
    obstacle: str,
    plan: dict,
    history: list[dict[str, str]],
    profile: dict | None = None,
) -> str:
    keys = api_keys_in_order()
    if not keys:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env or Streamlit secrets."
        )
    system_prompt = build_chat_system_prompt(
        goal, anchor, obstacle, plan, profile
    )
    # Keep recent turns to control tokens (system + last N messages)
    trimmed = history[-16:]
    errors: list[str] = []
    for i, key in enumerate(keys):
        try:
            return _call_chat(key, system_prompt, trimmed)
        except Exception as exc:  # noqa: BLE001
            label = "primary" if i == 0 else "fallback"
            errors.append(f"{label}: {exc}")
            continue
    raise RuntimeError("All API keys failed. " + " | ".join(errors))


def process_chat_turn(
    user_text: str,
    *,
    goal: str,
    anchor: str,
    obstacle: str,
    plan: dict,
    profile: dict | None,
) -> None:
    """Append a user message, call the coach, and show both bubbles."""
    st.session_state.chat_messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    with st.chat_message("assistant"):
        with st.spinner("Coach is thinking…"):
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat_messages
                    if m["role"] in ("user", "assistant")
                ]
                reply = chat_reply(
                    goal, anchor, obstacle, plan, history, profile
                )
            except Exception as exc:  # noqa: BLE001
                reply = f"Sorry, I couldn't reply just now: {exc}"
            st.markdown(reply)
    st.session_state.chat_messages.append({"role": "assistant", "content": reply})


def reset_chat(plan: dict, profile: dict | None = None) -> None:
    stack = plan.get("habit_stack") or "your habit stack"
    name = (profile or {}).get("name") or "there"
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": (
                f"Hi **{name}** — your plan is ready and locked to your profile. "
                f"Ask me anything about sticking with **{stack}**, busy days, "
                "or adjusting the 2-minute rule."
            ),
        }
    ]


def _on_who_change() -> None:
    """Switching identity clears the previous person's plan/chat/PDF."""
    new_id = st.session_state.get("who_user_id")
    if new_id == SELECT_PLACEHOLDER:
        new_id = None
    prev = st.session_state.get("active_user_id")
    if new_id != prev:
        st.session_state.active_user_id = new_id
        st.session_state.plan = None
        st.session_state.last_inputs = None
        st.session_state.chat_messages = []
        st.session_state.pdf_bytes = None
        st.session_state.pdf_ready = False


SELECT_PLACEHOLDER = "— Select your name —"


def law_meta(mode: str) -> list[tuple[str, str, str]]:
    """Return (key, label, law_name) for the four steps."""
    if mode == "break":
        return [
            ("cue", "Cue", "Make it Invisible"),
            ("craving", "Craving", "Make it Unattractive"),
            ("response", "Response", "Make it Difficult"),
            ("reward", "Reward", "Make it Unsatisfying"),
        ]
    return [
        ("cue", "Cue", "Make it Obvious"),
        ("craving", "Craving", "Make it Attractive"),
        ("response", "Response", "Make it Easy"),
        ("reward", "Reward", "Make it Satisfying"),
    ]


def render_admin_page() -> None:
    st.markdown('<p class="page-title">Admin · User knowledge base</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-pitch">Enter each attendee one by one. Their routine is stored in '
        "<code>data/users.json</code> and fed to the AI when they pick their name.</p>",
        unsafe_allow_html=True,
    )

    users = load_users()
    st.caption(f"{len(users)} profile(s) saved")

    with st.container(border=True):
        st.markdown("**Add or update a person**")
        edit_options = ["— New person —"] + [user_label(u) for u in users]
        edit_pick = st.selectbox("Edit existing", edit_options, key="admin_edit_pick")
        editing: dict | None = None
        if edit_pick != "— New person —":
            editing = next(
                (u for u in users if user_label(u) == edit_pick),
                None,
            )

        default_name = editing.get("name", "") if editing else ""
        default_role = editing.get("role", "") if editing else ""
        default_routine = editing.get("routine", "") if editing else ""
        default_notes = editing.get("notes", "") if editing else ""

        form_key = editing["id"] if editing else "new"
        name = st.text_input("Name", value=default_name, key=f"admin_name_{form_key}")
        role = st.text_input(
            "Role / team",
            value=default_role,
            placeholder="e.g. Engineer, Sales, Manager",
            key=f"admin_role_{form_key}",
        )
        routine = st.text_area(
            "Daily routine (knowledge base)",
            value=default_routine,
            height=120,
            placeholder="e.g. Wake 7am, coffee, WFH desk by 9, lunch 1pm, gym Mon/Wed…",
            key=f"admin_routine_{form_key}",
        )
        notes = st.text_area(
            "Extra notes (optional)",
            value=default_notes,
            height=80,
            placeholder="Personality, constraints, what usually derails them…",
            key=f"admin_notes_{form_key}",
        )

        save_col, del_col = st.columns(2)
        with save_col:
            if st.button("Save profile", type="primary", use_container_width=True):
                try:
                    saved = upsert_user(
                        name=name,
                        role=role,
                        routine=routine,
                        notes=notes,
                        user_id=editing["id"] if editing else None,
                    )
                    st.success(f"Saved: {saved['name']} (`{saved['id']}`)")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with del_col:
            if editing and st.button(
                "Delete this profile",
                use_container_width=True,
                key="admin_delete",
            ):
                delete_user(editing["id"])
                st.warning(f"Deleted {editing.get('name')}")
                st.rerun()

    if users:
        st.markdown("**Current roster**")
        for u in users:
            with st.expander(user_label(u)):
                st.write(f"**ID:** `{u.get('id')}`")
                st.write(f"**Role:** {user_display_role(u)}")
                st.write(f"**Routine:** {u.get('routine') or '—'}")
                st.write(f"**Notes:** {u.get('notes') or '—'}")
    else:
        st.info("No profiles yet — add your first attendee above.")


def main() -> None:
    st.set_page_config(
        page_title="Atomic Habits Coach",
        page_icon="⚡",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown(LINKTAL_CSS, unsafe_allow_html=True)

    if "plan" not in st.session_state:
        st.session_state.plan = None
    if "last_inputs" not in st.session_state:
        st.session_state.last_inputs = None
    if "view" not in st.session_state:
        st.session_state.view = "generate"
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "active_user_id" not in st.session_state:
        st.session_state.active_user_id = None

    with st.sidebar:
        st.markdown(
            '<p class="brand-title">Atomic Habits Coach</p>'
            '<p class="brand-sub">Book Sharing Tools</p>',
            unsafe_allow_html=True,
        )
        nav_options = ["Generate Plan", "Admin", "About"]
        view_map = {
            "Generate Plan": "generate",
            "Admin": "admin",
            "About": "about",
        }
        reverse_map = {v: k for k, v in view_map.items()}
        current_label = reverse_map.get(st.session_state.view, "Generate Plan")
        view = st.radio(
            "Navigation",
            options=nav_options,
            index=nav_options.index(current_label),
            label_visibility="collapsed",
        )
        st.session_state.view = view_map[view]
        sub = {
            "Generate Plan": "30-second habit builder",
            "Admin": "Enter attendee routines",
            "About": "Four Laws cheat sheet",
        }[view]
        st.markdown(
            '<div class="nav-item active" style="margin-top:0.5rem;">'
            f"{view}<span class=\"sub\">{sub}</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.caption("Internal · Friday book sharing")
        st.caption("Inspired by James Clear")

    if st.session_state.view == "admin":
        render_admin_page()
        return

    if st.session_state.view == "about":
        st.markdown('<p class="page-title">About</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="page-pitch">Core ideas from Atomic Habits — keep this cheat sheet handy.</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div class="card">
              <div class="law-label">The Habit Loop</div>
              <p class="law-body">Cue → Craving → Response → Reward</p>
              <p style="color:#6b7280;font-size:0.9rem;margin-top:0.75rem;">
                Every habit follows this loop. To change behavior, change one of the four stages.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        about_laws = [
            ("1. Make it Obvious", "Cue — habit stacking, clear cues in your environment."),
            ("2. Make it Attractive", "Craving — temptation bundling, join cultures where your desired behavior is normal."),
            ("3. Make it Easy", "Response — 2-minute rule, reduce friction, prepare your environment."),
            ("4. Make it Satisfying", "Reward — immediate rewards, habit trackers, never miss twice."),
        ]
        for i, (title, body) in enumerate(about_laws):
            with cols[i % 2]:
                st.markdown(
                    f'<div class="card"><div class="law-label">{title}</div>'
                    f'<p class="law-body">{body}</p></div>',
                    unsafe_allow_html=True,
                )
        st.markdown(
            """
            <div class="card">
              <div class="law-label">Quote</div>
              <p class="law-body" style="font-style:italic;">
                "You do not rise to the level of your goals. You fall to the level of your systems."
              </p>
              <p style="color:#9ca3af;font-size:0.8rem;margin-top:0.5rem;">— James Clear</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # --- Generate view ---
    _ensure_field_defaults()

    st.markdown(
        '<span class="step-hint">Pick your name · 3 questions · personal plan + chat</span>',
        unsafe_allow_html=True,
    )
    st.markdown('<p class="page-title">Your Habit Plan</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-pitch">Select your name first so the AI uses only your routine. '
        "Then answer three questions for your plan, PDF, and coach chat.</p>",
        unsafe_allow_html=True,
    )

    roster = load_users()
    id_to_user = {u["id"]: u for u in roster}
    who_options = [SELECT_PLACEHOLDER] + [u["id"] for u in roster]

    with st.container(border=True):
        st.markdown(
            '<p class="q-title">Who are you?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="field-label">Required — loads your personal knowledge base for AI</p>',
            unsafe_allow_html=True,
        )
        who_id = st.selectbox(
            "Who are you?",
            who_options,
            key="who_user_id",
            label_visibility="collapsed",
            format_func=lambda i: (
                SELECT_PLACEHOLDER
                if i == SELECT_PLACEHOLDER
                else id_to_user.get(i, {}).get("name", i)
            ),
            on_change=_on_who_change,
        )

        selected_profile = None
        if who_id and who_id != SELECT_PLACEHOLDER:
            selected_profile = id_to_user.get(who_id) or get_user(who_id)
            st.session_state.active_user_id = who_id
            if selected_profile:
                st.markdown(
                    f'<div class="success-bar">Signed in as '
                    f"<strong>{escape(selected_profile.get('name', ''))}</strong> — "
                    f"plan, PDF, and chat will use only your profile</div>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"**{user_display_role(selected_profile)}** · "
                    f"{(selected_profile.get('routine') or '')[:200]}"
                    f"{'…' if len(selected_profile.get('routine') or '') > 200 else ''}"
                )
        else:
            st.warning("Select your name to personalize the AI coach.")
            if not roster:
                st.caption("No profiles loaded — check `data/users.json` or use Admin.")

        st.markdown(
            '<p class="q-title">1. What do you want to build or break?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="field-label">Select one or more suggestions</p>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Habit suggestions",
            HABIT_SUGGESTIONS,
            key="goal_choice",
            label_visibility="collapsed",
            placeholder="Pick habits…",
            on_change=_sync_multi_to_text,
            args=("goal_choice", "goal_text"),
        )
        st.markdown(
            '<p class="field-label">Your answer (editable — add free text anytime)</p>',
            unsafe_allow_html=True,
        )
        st.text_area(
            "Habit answer",
            key="goal_text",
            height=80,
            placeholder="Selections appear here. Edit or add your own details…",
            label_visibility="collapsed",
        )

        st.markdown(
            '<p class="q-title">2. What is something that you do every day already? / '
            "Briefly explain your daily / weekends routines so that I can help you "
            "build or break habit better.</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="field-label">Select one or more suggestions</p>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Daily anchor suggestions",
            ANCHORS,
            key="anchor_choice",
            label_visibility="collapsed",
            placeholder="Pick daily routines…",
            on_change=_sync_multi_to_text,
            args=("anchor_choice", "anchor_text"),
        )
        st.markdown(
            '<p class="field-label">Your answer (editable — add free text anytime)</p>',
            unsafe_allow_html=True,
        )
        st.text_area(
            "Anchor answer",
            key="anchor_text",
            height=80,
            placeholder="Selections appear here. Edit or add your own details…",
            label_visibility="collapsed",
        )

        st.markdown(
            '<p class="q-title">3. What stops you from building or maintaining a good habit?</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="field-label">Select one or more suggestions</p>',
            unsafe_allow_html=True,
        )
        st.multiselect(
            "Obstacle suggestions",
            OBSTACLES,
            key="obstacle_choice",
            label_visibility="collapsed",
            placeholder="Pick blockers…",
            on_change=_sync_multi_to_text,
            args=("obstacle_choice", "obstacle_text"),
        )
        st.markdown(
            '<p class="field-label">Your answer (editable — add free text anytime)</p>',
            unsafe_allow_html=True,
        )
        st.text_area(
            "Obstacle answer",
            key="obstacle_text",
            height=80,
            placeholder="Selections appear here. Edit or add your own details…",
            label_visibility="collapsed",
        )

        submitted = st.button(
            "Generate my plan →",
            type="primary",
            use_container_width=True,
            key="generate_btn",
        )

    if submitted:
        goal = combine_for_ai(
            st.session_state.get("goal_choice") or [],
            st.session_state.get("goal_text") or "",
        )
        anchor = combine_for_ai(
            st.session_state.get("anchor_choice") or [],
            st.session_state.get("anchor_text") or "",
        )
        obstacle = combine_for_ai(
            st.session_state.get("obstacle_choice") or [],
            st.session_state.get("obstacle_text") or "",
        )
        if not selected_profile:
            st.error("Please select your name first so the coach can personalize for you.")
        elif not goal:
            st.error("Please select or type what you want to build or break.")
        elif not anchor:
            st.error("Please select or type something you already do every day.")
        elif not obstacle:
            st.error("Please select or type what usually stops you.")
        else:
            with st.spinner(
                f"Building {selected_profile.get('name')}'s 4-law plan..."
            ):
                try:
                    plan = generate_plan(
                        goal, anchor, obstacle, selected_profile
                    )
                    st.session_state.plan = plan
                    st.session_state.active_user_id = selected_profile.get("id")
                    st.session_state.last_inputs = {
                        "goal": goal,
                        "anchor": anchor,
                        "obstacle": obstacle,
                        "user_id": selected_profile.get("id"),
                        "profile": dict(selected_profile),
                    }
                    reset_chat(plan, selected_profile)
                    st.session_state.pdf_bytes = None
                    st.session_state.pdf_ready = False
                except Exception as exc:  # noqa: BLE001 — show user-friendly error
                    st.error(f"Could not generate plan: {exc}")
                    st.session_state.plan = None

    plan = st.session_state.plan
    inputs = st.session_state.last_inputs

    if plan and inputs:
        session_profile = inputs.get("profile") or (
            get_user(inputs["user_id"]) if inputs.get("user_id") else None
        )
        person_name = (session_profile or {}).get("name") or "You"
        mode = (plan.get("mode") or "build").lower()
        st.markdown(
            f'<div class="success-bar">✓ {escape(person_name)}\'s personalized plan is ready</div>',
            unsafe_allow_html=True,
        )

        stack = plan.get("habit_stack") or (
            f"After I {inputs['anchor']}, I will {plan.get('two_minute_habit', '...')}"
        )
        st.markdown(
            f'<div class="stack-highlight"><div class="stack-label">Habit Stack</div>'
            f"{escape(str(stack))}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="card"><div class="law-label">2-Minute Rule</div>'
            f'<p class="law-body">{escape(str(plan.get("two_minute_habit", "")))}</p></div>',
            unsafe_allow_html=True,
        )

        meta = law_meta(mode)
        # Stack to 1 column on narrow screens via CSS; 2 cols on desktop
        row1 = st.columns(2)
        row2 = st.columns(2)
        for i, (key, label, law) in enumerate(meta):
            col = row1[i] if i < 2 else row2[i - 2]
            with col:
                tip = plan.get(key, "")
                st.markdown(
                    f'<div class="card"><div class="law-label">{label}</div>'
                    f'<div class="law-law">{law}</div>'
                    f'<p class="law-body">{escape(str(tip))}</p></div>',
                    unsafe_allow_html=True,
                )

        st.markdown(
            f'<div class="card"><div class="law-label">Environment Design</div>'
            f'<p class="law-body">{escape(str(plan.get("environment_tip", "")))}</p></div>',
            unsafe_allow_html=True,
        )

        if "pdf_bytes" not in st.session_state:
            st.session_state.pdf_bytes = None
        if "pdf_ready" not in st.session_state:
            st.session_state.pdf_ready = False

        if st.button(
            "Download PDF →",
            type="primary",
            use_container_width=True,
            key="prep_pdf_btn",
        ):
            with st.spinner(f"Preparing {person_name}'s PDF…"):
                try:
                    st.session_state.pdf_bytes = build_pdf(
                        inputs["goal"],
                        inputs["anchor"],
                        plan,
                        person_name=person_name,
                        user_id=inputs.get("user_id"),
                    )
                    st.session_state.pdf_ready = True
                except Exception as exc:  # noqa: BLE001
                    st.session_state.pdf_ready = False
                    st.session_state.pdf_bytes = None
                    st.warning(f"PDF could not be generated: {exc}")

        if st.session_state.pdf_ready and st.session_state.pdf_bytes:
            st.success("PDF ready — tap below to save it to your device.")
            safe_name = "".join(
                c if c.isalnum() else "-" for c in person_name
            ).strip("-") or "habit"
            st.download_button(
                label="Save PDF to device →",
                data=st.session_state.pdf_bytes,
                file_name=f"atomic-habits-{safe_name}.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
                key="save_pdf_btn",
            )

        # --- Follow-up coach chat ---
        st.markdown("---")
        st.markdown(
            f'<p class="page-title" style="font-size:1.25rem;">Chat with {escape(person_name)}\'s coach</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="page-pitch">Private to <strong>{escape(person_name)}</strong> — '
            "answers use only your profile, 3 questions, and this plan.</p>",
            unsafe_allow_html=True,
        )

        if not st.session_state.chat_messages:
            reset_chat(plan, session_profile)

        _, clear_col = st.columns([4, 1])
        with clear_col:
            if st.button("Clear chat", key="clear_chat", use_container_width=True):
                reset_chat(plan, session_profile)
                st.rerun()

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if st.button(
            "Tell me what you know about me.",
            key="know_me_btn",
            use_container_width=True,
            type="primary",
        ):
            process_chat_turn(
                "Tell me what you know about me.",
                goal=inputs["goal"],
                anchor=inputs["anchor"],
                obstacle=inputs["obstacle"],
                plan=plan,
                profile=session_profile,
            )

        user_prompt = st.chat_input(f"Ask {person_name}'s Atomic Habits coach…")
        if user_prompt:
            process_chat_turn(
                user_prompt,
                goal=inputs["goal"],
                anchor=inputs["anchor"],
                obstacle=inputs["obstacle"],
                plan=plan,
                profile=session_profile,
            )


if __name__ == "__main__":
    main()
