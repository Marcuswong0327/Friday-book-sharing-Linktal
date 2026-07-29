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
from prompt import SYSTEM_PROMPT, build_user_prompt

load_dotenv()

HABIT_SUGGESTIONS = [
    "Read more books",
    "Exercise / work out",
    "Drink more water",
    "Meditate or journal",
    "Stop scrolling in bed",
    "Sleep earlier",
    "Eat healthier",
    "Type my own...",
]

ANCHORS = [
    "Drink morning coffee / tea",
    "Commute / arrive at work",
    "Sit at my desk",
    "Brush my teeth",
    "Finish lunch",
    "Put my phone on charge",
    "Type my own...",
]

OBSTACLES = [
    "Lack of time",
    "Forgetfulness",
    "Too tired",
    "No motivation",
    "Environment distractions",
    "Type my own...",
]

CUSTOM_OPTION = "Type my own..."


def resolve_field(choice: str, custom: str) -> str:
    """Prefer custom text when provided; otherwise use dropdown (unless 'Type my own')."""
    custom = (custom or "").strip()
    if custom:
        return custom
    if choice == CUSTOM_OPTION:
        return ""
    return choice


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

div[data-testid="stForm"] {
  background: #ffffff;
  border: 1px solid var(--ah-border);
  border-radius: 8px;
  padding: 1.2rem 1.25rem 1.05rem 1.25rem !important;
}

div[data-testid="stForm"] .stTextInput > div > div,
div[data-testid="stForm"] .stSelectbox > div > div,
div[data-testid="stForm"] .stTextArea > div > div {
  min-height: 44px !important;
}
div[data-testid="stForm"] input,
div[data-testid="stForm"] textarea,
div[data-testid="stForm"] [data-baseweb="select"] > div {
  min-height: 44px !important;
  background-color: #ffffff !important;
  color: var(--ah-text) !important;
  border: 1px solid #d1d5db !important;
  border-radius: 8px !important;
  font-size: 0.95rem !important;
  box-shadow: none !important;
}
div[data-testid="stForm"] textarea {
  min-height: 72px !important;
  line-height: 1.4 !important;
}
div[data-testid="stForm"] input:focus,
div[data-testid="stForm"] textarea:focus,
div[data-testid="stForm"] [data-baseweb="select"] > div:focus-within {
  border-color: var(--ah-purple) !important;
  box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.15) !important;
}
div[data-testid="stForm"] label,
div[data-testid="stForm"] [data-testid="stWidgetLabel"] p {
  font-size: 0.9rem !important;
  font-weight: 600 !important;
  color: #374151 !important;
}
div[data-testid="stForm"] [data-testid="stVerticalBlock"] {
  gap: 0.55rem !important;
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


def _call_model(api_key: str, goal: str, anchor: str, obstacle: str) -> dict:
    client = make_client(api_key)
    response = client.chat.completions.create(
        model=resolve_model(api_key),
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(goal, anchor, obstacle)},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return parse_plan_json(content)


def generate_plan(goal: str, anchor: str, obstacle: str) -> dict:
    keys = api_keys_in_order()
    if not keys:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env or Streamlit secrets."
        )
    errors: list[str] = []
    for i, key in enumerate(keys):
        try:
            return _call_model(key, goal, anchor, obstacle)
        except Exception as exc:  # noqa: BLE001 — try next key
            label = "primary" if i == 0 else "fallback"
            errors.append(f"{label}: {exc}")
            continue
    raise RuntimeError(
        "All API keys failed. " + " | ".join(errors)
    )


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

    with st.sidebar:
        st.markdown(
            '<p class="brand-title">Atomic Habits Coach</p>'
            '<p class="brand-sub">Book Sharing Tools</p>',
            unsafe_allow_html=True,
        )
        view = st.radio(
            "Navigation",
            options=["Generate Plan", "About"],
            index=0 if st.session_state.view == "generate" else 1,
            label_visibility="collapsed",
        )
        st.session_state.view = "generate" if view == "Generate Plan" else "about"
        st.markdown(
            '<div class="nav-item active" style="margin-top:0.5rem;">'
            f'{view}<span class="sub">'
            f'{"30-second habit builder" if view == "Generate Plan" else "Four Laws cheat sheet"}'
            "</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.caption("Internal · Friday book sharing")
        st.caption("Inspired by James Clear")

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
    st.markdown(
        '<span class="step-hint">3 quick questions · under 30 seconds</span>',
        unsafe_allow_html=True,
    )
    st.markdown('<p class="page-title">Your Habit Plan</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-pitch">Answer three questions. Get a 4-law action plan you can download as a PDF.</p>',
        unsafe_allow_html=True,
    )

    with st.form("habit_form", clear_on_submit=False):
        st.markdown("**1. What do you want to build or break?**")
        goal_choice = st.selectbox(
            "Suggested habits",
            HABIT_SUGGESTIONS,
            label_visibility="collapsed",
            key="goal_choice",
        )
        goal_custom = st.text_area(
            "Or type your own",
            placeholder="e.g. Stop checking email after 9pm",
            height=68,
            label_visibility="collapsed",
            key="goal_custom",
        )
        st.caption("Pick a suggestion above, or type your own habit in the box.")

        st.markdown("**2. What is something that you do every day already?**")
        anchor_choice = st.selectbox(
            "Daily anchors",
            ANCHORS,
            label_visibility="collapsed",
            key="anchor_choice",
        )
        anchor_custom = st.text_area(
            "Custom daily anchor",
            placeholder="e.g. Pour my first cup of tea",
            height=68,
            label_visibility="collapsed",
            key="anchor_custom",
        )
        st.caption("Choose from the list, or write your own routine.")

        st.markdown(
            "**3. What stops you from building or maintaining a good habit?**"
        )
        obstacle_choice = st.selectbox(
            "Obstacles",
            OBSTACLES,
            label_visibility="collapsed",
            key="obstacle_choice",
        )
        obstacle_custom = st.text_area(
            "Custom obstacle",
            placeholder="e.g. Kids wake up early / Meetings run late",
            height=68,
            label_visibility="collapsed",
            key="obstacle_custom",
        )
        st.caption("Pick a common blocker, or describe yours.")

        submitted = st.form_submit_button(
            "Generate my plan →",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        goal = resolve_field(goal_choice, goal_custom)
        anchor = resolve_field(anchor_choice, anchor_custom)
        obstacle = resolve_field(obstacle_choice, obstacle_custom)
        if not goal:
            st.error("Please choose or type what you want to build or break.")
        elif not anchor:
            st.error("Please choose or type something you already do every day.")
        elif not obstacle:
            st.error("Please choose or type what usually stops you.")
        else:
            with st.spinner("Building your 4-law plan..."):
                try:
                    plan = generate_plan(goal, anchor, obstacle)
                    st.session_state.plan = plan
                    st.session_state.last_inputs = {
                        "goal": goal,
                        "anchor": anchor,
                        "obstacle": obstacle,
                    }
                except Exception as exc:  # noqa: BLE001 — show user-friendly error
                    st.error(f"Could not generate plan: {exc}")
                    st.session_state.plan = None

    plan = st.session_state.plan
    inputs = st.session_state.last_inputs

    if plan and inputs:
        mode = (plan.get("mode") or "build").lower()
        st.markdown(
            '<div class="success-bar">✓ Your personalized plan is ready</div>',
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

        try:
            pdf_bytes = build_pdf(inputs["goal"], inputs["anchor"], plan)
            st.download_button(
                label="Download PDF →",
                data=pdf_bytes,
                file_name="atomic-habits-plan.pdf",
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )
        except Exception as exc:  # noqa: BLE001
            st.warning(f"PDF could not be generated: {exc}")


if __name__ == "__main__":
    main()
