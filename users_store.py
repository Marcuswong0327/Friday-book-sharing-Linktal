"""Load / save attendee profiles in data/users.json (Friday knowledge base)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
USERS_PATH = DATA_DIR / "users.json"


def _empty_store() -> dict[str, Any]:
    return {"users": []}


def ensure_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_PATH.exists():
        USERS_PATH.write_text(
            json.dumps(_empty_store(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def load_users() -> list[dict[str, Any]]:
    ensure_store()
    try:
        raw = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    users = raw.get("users") if isinstance(raw, dict) else None
    if not isinstance(users, list):
        return []
    return [u for u in users if isinstance(u, dict) and u.get("id") and u.get("name")]


def save_users(users: list[dict[str, Any]]) -> None:
    ensure_store()
    payload = {"users": users}
    USERS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return base or "user"


def unique_id(name: str, existing: list[dict[str, Any]], exclude_id: str | None = None) -> str:
    base = slugify(name)
    ids = {u.get("id") for u in existing if u.get("id") != exclude_id}
    if base not in ids:
        return base
    n = 2
    while f"{base}-{n}" in ids:
        n += 1
    return f"{base}-{n}"


def get_user(user_id: str) -> dict[str, Any] | None:
    for user in load_users():
        if user.get("id") == user_id:
            return user
    return None


def upsert_user(
    *,
    name: str,
    role: str,
    routine: str,
    notes: str = "",
    user_id: str | None = None,
) -> dict[str, Any]:
    users = load_users()
    name = name.strip()
    if not name:
        raise ValueError("Name is required.")

    if user_id:
        for i, user in enumerate(users):
            if user.get("id") == user_id:
                users[i] = {
                    "id": user_id,
                    "name": name,
                    "role": role.strip(),
                    "routine": routine.strip(),
                    "notes": notes.strip(),
                }
                save_users(users)
                return users[i]
        raise ValueError(f"User id not found: {user_id}")

    new_user = {
        "id": unique_id(name, users),
        "name": name,
        "role": role.strip(),
        "routine": routine.strip(),
        "notes": notes.strip(),
    }
    users.append(new_user)
    save_users(users)
    return new_user


def delete_user(user_id: str) -> bool:
    users = load_users()
    next_users = [u for u in users if u.get("id") != user_id]
    if len(next_users) == len(users):
        return False
    save_users(next_users)
    return True


def format_profile_for_prompt(user: dict[str, Any] | None) -> str:
    if not user:
        return "No saved profile selected (treat as a guest)."
    return (
        f"Name: {user.get('name', '')}\n"
        f"Role / team: {user.get('role', '')}\n"
        f"Known daily routine: {user.get('routine', '')}\n"
        f"Extra notes: {user.get('notes', '') or '(none)'}"
    )


def user_label(user: dict[str, Any]) -> str:
    """Short label for dropdowns — name only (roles can be long)."""
    return str(user.get("name") or user.get("id") or "Unknown")


def user_display_role(user: dict[str, Any]) -> str:
    role = (user.get("role") or "").strip()
    return role if role else "Linktal teammate"
