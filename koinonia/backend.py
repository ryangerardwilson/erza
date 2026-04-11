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


def _rpc(name: str, **params: Any) -> Any:
    return _supabase_request("POST", f"rpc/{name}", body=params)


def _normalize_handle(raw: str) -> str:
    normalized = raw.strip().lower().lstrip("@")
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    return normalized or "resident"


def _profile_link(handle: str) -> str:
    return "index.erza"


def _thread_link(slug: str) -> str:
    return "index.erza"


def _set_status(message: str) -> None:
    session()["ui_status"] = message


def _status() -> str:
    return session().get(
        "ui_status",
        "Koinonia now behaves like a single-screen erza app with tabs that shift around your login state.",
    )


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
            "select": "display_name,handle,bio,primary_circle,followers",
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


def _followed_handles(viewer_handle: str | None) -> set[str]:
    if not viewer_handle:
        return set()
    rows = _rows(
        "follow_relations",
        query={
            "select": "followed_handle",
            "follower_handle": f"eq.{viewer_handle}",
        },
    )
    return {str(row["followed_handle"]) for row in rows}


def _following_state(viewer_handle: str | None, target_handle: str) -> bool:
    if not viewer_handle or viewer_handle == target_handle:
        return False
    row = _one(
        "follow_relations",
        query={
            "select": "followed_handle",
            "follower_handle": f"eq.{viewer_handle}",
            "followed_handle": f"eq.{target_handle}",
        },
    )
    return row is not None


def _post_card(row: dict[str, Any]) -> dict[str, Any]:
    handle = str(row["handle"])
    slug = str(row["slug"])
    return {
        "id": int(row["id"]),
        "slug": slug,
        "author": str(row["author"]),
        "handle": handle,
        "circle": str(row["circle"]),
        "body": str(row["body"]),
        "likes": int(row["likes"]),
        "boosts": int(row["boosts"]),
        "reply_count": int(row["reply_count"]),
        "profile_link": _profile_link(handle),
        "thread_link": _thread_link(slug),
    }


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
        "profile_link": _profile_link(account["handle"]),
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
            "bio": "",
            "primary_circle": "",
            "followers": 0,
            "following": False,
            "can_follow": False,
            "is_self": False,
            "follow_action_label": "Follow",
            "posts": [],
        }
    return profiles_by_handle(account["handle"])


@handler("network.overview")
def network_overview() -> dict[str, int]:
    row = _one(
        "network_overview_view",
        query={"select": "posts,circles,people"},
    )
    if row is None:
        return {"posts": 0, "circles": 0, "people": 0}
    return {
        "posts": int(row["posts"]),
        "circles": int(row["circles"]),
        "people": int(row["people"]),
    }


@handler("feed.timeline")
def feed_timeline() -> list[dict[str, Any]]:
    rows = _rows(
        "feed_timeline_view",
        query={
            "select": "id,slug,author,handle,circle,body,likes,boosts,reply_count,created_at",
            "order": "created_at.desc",
        },
    )
    return [_post_card(row) for row in rows]


@handler("circles.list")
def circles_list() -> list[dict[str, str]]:
    rows = _rows(
        "circles",
        query={"select": "name,rhythm", "order": "sort_order.asc"},
    )
    return [{"name": str(row["name"]), "rhythm": str(row["rhythm"])} for row in rows]


@handler("people.suggested")
def people_suggested() -> list[dict[str, Any]]:
    account = _current_account()
    viewer_handle = account["handle"] if account is not None else None
    followed_handles = _followed_handles(viewer_handle)
    rows = _rows(
        "profiles",
        query={
            "select": "display_name,handle,bio,primary_circle,followers",
            "order": "followers.desc",
            "limit": "3",
        },
    )
    people = []
    for row in rows:
        handle = str(row["handle"])
        can_follow = viewer_handle is not None and viewer_handle != handle
        following = handle in followed_handles
        people.append(
            {
                "name": str(row["display_name"]),
                "handle": handle,
                "bio": str(row["bio"]),
                "primary_circle": str(row["primary_circle"]),
                "following": following,
                "can_follow": can_follow,
                "follow_action_label": "Unfollow" if following else "Follow",
                "profile_link": _profile_link(handle),
            }
        )
    return people


@handler("signals.list")
def signals_list() -> list[dict[str, Any]]:
    rows = _rows(
        "signals_view",
        query={"select": "tag,count", "order": "count.desc", "limit": "6"},
    )
    return [{"tag": str(row["tag"]), "count": int(row["count"])} for row in rows]


@handler("threads.by_slug")
def threads_by_slug(slug: str) -> dict[str, Any]:
    row = _one(
        "feed_timeline_view",
        query={
            "select": "id,slug,author,handle,circle,body,likes,boosts,reply_count,created_at",
            "slug": f"eq.{slug}",
        },
    )
    if row is None:
        return {
            "id": 0,
            "slug": slug,
            "author": "Unavailable",
            "handle": "missing",
            "circle": "unknown",
            "body": "That thread has not landed in this prototype yet.",
            "likes": 0,
            "boosts": 0,
            "reply_count": 0,
            "profile_link": "index.erza",
            "thread_link": "index.erza",
            "replies": [],
        }

    replies = _rows(
        "replies",
        query={
            "select": "author_name,author_handle,body,created_at",
            "thread_slug": f"eq.{slug}",
            "order": "created_at.asc",
        },
    )
    thread = _post_card(row)
    thread["replies"] = [
        {
            "author": str(reply["author_name"]),
            "handle": str(reply["author_handle"]),
            "body": str(reply["body"]),
        }
        for reply in replies
    ]
    return thread


@handler("profiles.by_handle")
def profiles_by_handle(handle: str) -> dict[str, Any]:
    normalized = _normalize_handle(handle)
    account = _current_account()
    viewer_handle = account["handle"] if account is not None else None
    profile = _profile_row(normalized)
    if profile is None:
        return {
            "name": "Unknown resident",
            "handle": normalized,
            "bio": "This profile has not been authored yet.",
            "primary_circle": "unassigned",
            "followers": 0,
            "following": False,
            "can_follow": False,
            "is_self": False,
            "follow_action_label": "Follow",
            "posts": [],
        }

    posts = _rows(
        "feed_timeline_view",
        query={
            "select": "id,slug,author,handle,circle,body,likes,boosts,reply_count,created_at",
            "handle": f"eq.{normalized}",
            "order": "created_at.desc",
        },
    )
    is_self = viewer_handle == normalized
    following = _following_state(viewer_handle, normalized)
    return {
        "name": str(profile["display_name"]),
        "handle": str(profile["handle"]),
        "bio": str(profile["bio"]),
        "primary_circle": str(profile["primary_circle"]),
        "followers": int(profile["followers"]),
        "following": following,
        "can_follow": viewer_handle is not None and not is_self,
        "is_self": is_self,
        "follow_action_label": "Unfollow builder" if following else "Follow builder",
        "posts": [_post_card(post) for post in posts],
    }


@handler("mission.highlights")
def mission_highlights() -> list[dict[str, str]]:
    return [
        {
            "title": "One screen, clear tabs",
            "body": "Koinonia now stays in one erza file and lets the top tabs shift with the viewer's state instead of hopping between linked pages.",
        },
        {
            "title": "Claimed identities",
            "body": "Any unclaimed username can be claimed once. After that, the same password is required to reopen that account.",
        },
        {
            "title": "Post from where you are",
            "body": "Both the feed and profile tabs open with a post form so the social loop starts inside the active page, not in a separate compose route.",
        },
    ]


@handler("feed.like")
def feed_like(post_id: int) -> None:
    account = _current_account()
    if account is None:
        _set_status("Sign in first to signal dispatches.")
        return
    _rpc("increment_post_like", post_id=int(post_id))
    _set_status(f"@{account['handle']} signaled dispatch {post_id}.")


@handler("feed.boost")
def feed_boost(post_id: int) -> None:
    account = _current_account()
    if account is None:
        _set_status("Sign in first to boost dispatches.")
        return
    _rpc("increment_post_boost", post_id=int(post_id))
    _set_status(f"@{account['handle']} boosted dispatch {post_id}.")


@handler("people.toggle_follow")
def people_toggle_follow(handle: str) -> None:
    account = _current_account()
    if account is None:
        _set_status("Sign in first to follow builders.")
        return
    normalized = _normalize_handle(handle)
    if normalized == account["handle"]:
        _set_status("That account is already you.")
        return
    result = _rpc(
        "toggle_profile_follow",
        viewer_handle=account["handle"],
        profile_handle=normalized,
    )
    state = False
    if isinstance(result, bool):
        state = result
    elif isinstance(result, str):
        state = result.lower() == "true"
    _set_status(f"{'Following' if state else 'Stopped following'} @{normalized}.")


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


@route("/auth/signup")
def auth_signup(username: str = "", password: str = ""):
    return _access_account(username, password)


@route("/auth/login")
def auth_login(username: str = "", password: str = ""):
    return _access_account(username, password)


@route("/posts")
def create_post(body: str = ""):
    account = _current_account()
    if account is None:
        return error("Sign in first to publish.")
    if not body.strip():
        return error("Dispatch is required.")
    _rpc(
        "create_dispatch",
        author_name=account["display_name"],
        profile_handle=account["handle"],
        body=body.strip(),
    )
    _set_status(f"Published a new dispatch as @{account['handle']}.")
    return redirect("index.erza")


@route("/threads/launch-week/reply")
def reply_launch_week(body: str = ""):
    return _append_reply("launch-week", body)


@route("/threads/pattern-language/reply")
def reply_pattern_language(body: str = ""):
    return _append_reply("pattern-language", body)


def _append_reply(slug: str, body: str):
    account = _current_account()
    if account is None:
        return error("Sign in first to reply.")
    if not body.strip():
        return error("Reply text is required.")
    _rpc(
        "add_thread_reply",
        thread_slug=slug,
        author_name=account["display_name"],
        profile_handle=account["handle"],
        body=body.strip(),
    )
    _set_status(f"Replied to {slug} as @{account['handle']}.")
    return redirect("index.erza")
