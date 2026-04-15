from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from erza.backend import error, handler, redirect, route, session


class SupabaseError(RuntimeError):
    """Raised when Koinonia cannot complete a Supabase request."""


PROFILE_STATE_PREFIX = "koinonia-profile-v1:"
MAX_PROFILE_DESCRIPTION_LENGTH = 160
MAX_FEED_THREADS = 20
MAX_PROFILE_THREADS = 8
DEFAULT_PROFILE_PICTURE = "\n".join(
    [
        "  .--.",
        " /_.._\\\\",
        "( o  o )",
        " | .. |",
        " |____|",
    ]
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SupabaseError(f"missing required environment variable: {name}")
    return value


def _supabase_base_url() -> str:
    return _env("KOINONIA_SUPABASE_URL").rstrip("/") + "/rest/v1"


def _supabase_headers(
    *,
    accept_object: bool = False,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    key = _env("KOINONIA_SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if accept_object:
        headers["Accept"] = "application/vnd.pgrst.object+json"
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _supabase_request(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | list[dict[str, Any]] | None = None,
    accept_object: bool = False,
    extra_headers: dict[str, str] | None = None,
) -> Any:
    url = f"{_supabase_base_url()}/{path.lstrip('/')}"
    if query:
        url += "?" + urlencode(query, doseq=True)

    request = Request(
        url,
        headers=_supabase_headers(accept_object=accept_object, extra_headers=extra_headers),
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        method=method,
    )
    try:
        with urlopen(request, timeout=15.0) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SupabaseError(detail or f"supabase request failed: {exc.code}") from exc
    except URLError as exc:
        raise SupabaseError("failed to reach Supabase") from exc

    if not payload.strip():
        return None
    return json.loads(payload)


def _rows(path: str, *, query: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _supabase_request("GET", path, query=query)
    if not isinstance(payload, list):
        raise SupabaseError(f"unexpected Supabase response for {path}")
    return payload


def _one(path: str, *, query: dict[str, Any]) -> dict[str, Any] | None:
    rows = _rows(path, query=query)
    if not rows:
        return None
    return rows[0]


def _insert(path: str, body: dict[str, Any] | list[dict[str, Any]]) -> Any:
    return _supabase_request(
        "POST",
        path,
        body=body,
        extra_headers={"Prefer": "return=minimal"},
    )


def _update(path: str, *, query: dict[str, Any], body: dict[str, Any]) -> Any:
    return _supabase_request(
        "PATCH",
        path,
        query=query,
        body=body,
        extra_headers={"Prefer": "return=minimal"},
    )


def _rpc(name: str, **params: Any) -> Any:
    return _supabase_request("POST", f"rpc/{name}", body=params)


def _normalize_handle(raw: str) -> str:
    normalized = raw.strip().lower().lstrip("@")
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    return normalized or "resident"


def _set_status(message: str) -> None:
    session()["ui_status"] = message


def _status() -> str:
    return session().get(
        "ui_status",
        "Koinonia is a single town square for posts, replies, and small terminal-native threads.",
    )


def _decode_profile_state(raw_bio: str) -> dict[str, str]:
    stored = str(raw_bio or "")
    if stored.startswith(PROFILE_STATE_PREFIX):
        payload_text = stored[len(PROFILE_STATE_PREFIX) :]
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            payload = {}
        description = str(payload.get("description", "")).strip()
        picture = _normalize_profile_picture(str(payload.get("picture", "")))
        return {"description": description, "picture": picture}
    return {
        "description": stored.strip(),
        "picture": DEFAULT_PROFILE_PICTURE,
    }


def _encode_profile_state(description: str, picture: str) -> str:
    return PROFILE_STATE_PREFIX + json.dumps(
        {
            "description": description,
            "picture": picture,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _normalize_profile_picture(raw_picture: str) -> str:
    normalized = str(raw_picture or "").replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).strip("\n")
    if not normalized.strip():
        return DEFAULT_PROFILE_PICTURE
    return normalized


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
    )
    return "scrypt$%s$%s" % (
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_b64, digest_b64 = encoded.split("$", 2)
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False
    salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
    expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
    )
    return hmac.compare_digest(actual, expected)


def _profile_row(handle: str) -> dict[str, Any] | None:
    return _one(
        "profiles",
        query={
            "select": "display_name,handle,bio,created_at",
            "handle": f"eq.{handle}",
        },
    )


def _account_row(handle: str) -> dict[str, Any] | None:
    return _one(
        "accounts",
        query={
            "select": "handle,password_hash,created_at",
            "handle": f"eq.{handle}",
        },
    )


def _login_session(handle: str) -> None:
    profile = _profile_row(handle)
    display_name = handle
    if profile is not None:
        display_name = str(profile["display_name"])
    state = session()
    state["auth_handle"] = handle
    state["auth_display_name"] = display_name


def _logout_session() -> None:
    state = session()
    state.pop("auth_handle", None)
    state.pop("auth_display_name", None)


def _current_account() -> dict[str, str] | None:
    state = session()
    handle = str(state.get("auth_handle", "")).strip()
    if not handle:
        return None
    display_name = str(state.get("auth_display_name", "")).strip()
    if display_name:
        return {"handle": handle, "display_name": display_name}
    profile = _profile_row(handle)
    if profile is None:
        _logout_session()
        return None
    display_name = str(profile["display_name"])
    state["auth_display_name"] = display_name
    return {"handle": handle, "display_name": display_name}


def _post_card(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "slug": str(row["slug"]),
        "handle": str(row["handle"]),
        "body": str(row["body"]),
        "likes": int(row["likes"]),
        "reply_count": int(row["reply_count"]),
        "replies": [],
    }


def _reply_card(row: dict[str, Any]) -> dict[str, Any]:
    parent_reply_id = row.get("parent_reply_id")
    return {
        "id": int(row["id"]),
        "thread_slug": str(row["thread_slug"]),
        "parent_reply_id": int(parent_reply_id) if parent_reply_id is not None else None,
        "handle": str(row["handle"]),
        "body": str(row["body"]),
        "likes": int(row["likes"]),
        "reply_count": int(row["reply_count"]),
        "replies": [],
    }


def _supabase_text_list(values: list[str]) -> str:
    quoted = ['"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"' for value in values]
    return f"in.({','.join(quoted)})"


def _friendly_supabase_error_message(exc: SupabaseError) -> str:
    raw = str(exc).strip()
    if not raw:
        return "Koinonia could not complete that request."
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict):
        message = str(payload.get("message", "")).strip()
        if message:
            return message
    return raw


def _attach_replies(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not posts:
        return posts

    slugs = [str(post["slug"]) for post in posts]
    reply_rows = _rows(
        "thread_replies_view",
        query={
            "select": "id,thread_slug,parent_reply_id,handle,body,likes,reply_count,created_at",
            "thread_slug": _supabase_text_list(slugs),
            "order": "created_at.asc",
        },
    )

    top_level_by_thread: dict[str, list[dict[str, Any]]] = {slug: [] for slug in slugs}
    top_level_by_id: dict[int, dict[str, Any]] = {}
    for row in reply_rows:
        reply = _reply_card(row)
        parent_reply_id = reply["parent_reply_id"]
        if parent_reply_id is None:
            top_level_by_thread.setdefault(reply["thread_slug"], []).append(reply)
            top_level_by_id[reply["id"]] = reply
            continue
        parent = top_level_by_id.get(parent_reply_id)
        if parent is not None:
            parent["replies"].append(reply)

    for post in posts:
        post["replies"] = top_level_by_thread.get(str(post["slug"]), [])
    return posts


def _load_posts(*, limit: int, author_handle: str | None = None) -> list[dict[str, Any]]:
    query = {
        "select": "id,slug,handle,body,likes,reply_count,created_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if author_handle is not None:
        query["handle"] = f"eq.{author_handle}"
    rows = _rows("feed_timeline_view", query=query)
    return _attach_replies([_post_card(row) for row in rows])


@handler("ui.status")
def ui_status() -> str:
    return _status()


@handler("auth.viewer")
def auth_viewer() -> dict[str, Any]:
    account = _current_account()
    if account is None:
        return {
            "logged_in": False,
            "handle": "",
            "display_name": "",
            "profile_link": "index.erza",
        }
    return {
        "logged_in": True,
        "handle": account["handle"],
        "display_name": account["display_name"],
        "profile_link": "index.erza",
    }


@handler("auth.logout")
def auth_logout() -> None:
    account = _current_account()
    _logout_session()
    if account is None:
        _set_status("No account is currently signed in.")
        return
    _set_status(f"Logged out of @{account['handle']}.")


@handler("profiles.current")
def profiles_current() -> dict[str, Any]:
    account = _current_account()
    if account is None:
        return {
            "name": "",
            "handle": "",
            "description": "",
            "bio": "",
            "picture": DEFAULT_PROFILE_PICTURE,
            "posts": [],
        }
    return profiles_by_handle(account["handle"])


@handler("network.overview")
def network_overview() -> dict[str, int]:
    row = _one(
        "network_overview_view",
        query={"select": "posts,replies,people"},
    )
    if row is None:
        return {"posts": 0, "replies": 0, "people": 0}
    return {
        "posts": int(row["posts"]),
        "replies": int(row["replies"]),
        "people": int(row["people"]),
    }


@handler("feed.timeline")
def feed_timeline() -> list[dict[str, Any]]:
    return _load_posts(limit=MAX_FEED_THREADS)


@handler("profiles.by_handle")
def profiles_by_handle(handle: str) -> dict[str, Any]:
    normalized = _normalize_handle(handle)
    profile = _profile_row(normalized)
    if profile is None:
        return {
            "name": normalized,
            "handle": normalized,
            "description": "",
            "bio": "",
            "picture": DEFAULT_PROFILE_PICTURE,
            "posts": [],
        }

    profile_state = _decode_profile_state(str(profile["bio"]))
    return {
        "name": str(profile["display_name"]),
        "handle": str(profile["handle"]),
        "description": profile_state["description"],
        "bio": profile_state["description"],
        "picture": profile_state["picture"],
        "posts": _load_posts(limit=MAX_PROFILE_THREADS, author_handle=normalized),
    }


@handler("mission.highlights")
def mission_highlights() -> list[dict[str, str]]:
    return [
        {
            "title": "One town square",
            "body": "Every post lands in the same shared feed instead of disappearing into circles or sub-communities.",
        },
        {
            "title": "Simple identity",
            "body": "Any unclaimed username can be claimed once, and the same password reopens that account later.",
        },
        {
            "title": "Shallow threads",
            "body": "Replies can target a post or a reply, but the nesting stops there so each thread stays readable in the terminal.",
        },
    ]


@handler("feed.like")
def feed_like(post_id: int | None = None, reply_id: int | None = None) -> None:
    account = _current_account()
    if account is None:
        _set_status("Sign in first to like posts and replies.")
        return
    if post_id is not None:
        _rpc("increment_post_like", post_id=int(post_id))
        _set_status(f"@{account['handle']} liked post {int(post_id)}.")
        return
    if reply_id is not None:
        _rpc("increment_reply_like", reply_id=int(reply_id))
        _set_status(f"@{account['handle']} liked reply {int(reply_id)}.")
        return
    _set_status("Nothing to like.")


def _access_account(username: str = "", password: str = ""):
    raw_username = username.strip()
    normalized = _normalize_handle(raw_username)
    password = password.strip()
    if not raw_username:
        return error("Username is required.")
    if len(password) < 4:
        return error("Password must be at least 4 characters.")

    existing_account = _account_row(normalized)
    if existing_account is not None:
        if not _verify_password(password, str(existing_account["password_hash"])):
            return error("Invalid password for that username.")
        _login_session(normalized)
        _set_status(f"Signed in as @{normalized}.")
        return redirect("index.erza")

    _rpc(
        "ensure_koinonia_profile",
        author_name=normalized,
        profile_handle=normalized,
    )
    try:
        _insert(
            "accounts",
            {
                "handle": normalized,
                "password_hash": _hash_password(password),
            },
        )
    except SupabaseError as exc:
        if "duplicate key" in str(exc).lower():
            return error("That username is already claimed.")
        raise

    _login_session(normalized)
    _set_status(f"Claimed @{normalized}.")
    return redirect("index.erza")


@route("/auth/access")
def auth_access(username: str = "", password: str = ""):
    return _access_account(username, password)


@route("/.well-known/erza/auth")
def erza_auth(username: str = "", password: str = ""):
    return _access_account(username, password)


@route("/posts")
def create_post(body: str = ""):
    account = _current_account()
    if account is None:
        return error("Sign in first to publish.")
    if not body.strip():
        return error("Post text is required.")
    try:
        _rpc(
            "create_post",
            author_name=account["display_name"],
            profile_handle=account["handle"],
            body=body.strip(),
        )
    except SupabaseError as exc:
        return error(_friendly_supabase_error_message(exc))
    _set_status(f"Posted to the town square as @{account['handle']}.")
    return redirect("index.erza")


@route("/threads/reply")
def create_thread_reply(
    thread_slug: str = "",
    parent_reply_id: str = "",
    body: str = "",
):
    account = _current_account()
    if account is None:
        return error("Sign in first to reply.")
    if not thread_slug.strip():
        return error("Thread target is required.")
    if not body.strip():
        return error("Reply text is required.")

    parent_value = parent_reply_id.strip()
    try:
        parent_id = int(parent_value) if parent_value else None
    except ValueError:
        return error("Reply target is invalid.")

    try:
        _rpc(
            "add_thread_reply",
            thread_slug=thread_slug.strip(),
            parent_reply_id=parent_id,
            author_name=account["display_name"],
            profile_handle=account["handle"],
            body=body.strip(),
        )
    except SupabaseError as exc:
        return error(_friendly_supabase_error_message(exc))
    _set_status(f"Replied as @{account['handle']}.")
    return redirect("index.erza")


@route("/profile/edit")
def update_profile(description: str | None = None, profile_picture: str | None = None, bio: str | None = None):
    account = _current_account()
    if account is None:
        return error("Sign in first to update your profile.")

    current_profile = _profile_row(account["handle"])
    current_state = _decode_profile_state(str(current_profile["bio"])) if current_profile is not None else {
        "description": "",
        "picture": DEFAULT_PROFILE_PICTURE,
    }
    next_description = (
        description if description is not None else bio if bio is not None else current_state["description"]
    ).strip()
    if len(next_description) > MAX_PROFILE_DESCRIPTION_LENGTH:
        return error(f"Description must stay within {MAX_PROFILE_DESCRIPTION_LENGTH} characters.")
    next_picture = _normalize_profile_picture(
        profile_picture if profile_picture is not None else current_state["picture"]
    )

    _update(
        "profiles",
        query={"handle": f"eq.{account['handle']}"},
        body={"bio": _encode_profile_state(next_description, next_picture)},
    )
    _set_status(f"Updated @{account['handle']}'s profile.")
    return redirect("index.erza")
