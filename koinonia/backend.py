from __future__ import annotations

import json
import os
import re
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


def _supabase_headers(*, accept_object: bool = False) -> dict[str, str]:
    key = _env("KOINONIA_SUPABASE_SERVICE_ROLE_KEY")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if accept_object:
        headers["Accept"] = "application/vnd.pgrst.object+json"
    return headers


def _supabase_request(
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    accept_object: bool = False,
) -> Any:
    url = f"{_supabase_base_url()}/{path.lstrip('/')}"
    if query:
        url += "?" + urlencode(query, doseq=True)

    request = Request(
        url,
        headers=_supabase_headers(accept_object=accept_object),
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


def _rpc(name: str, **params: Any) -> Any:
    return _supabase_request("POST", f"rpc/{name}", body=params)


def _normalize_handle(raw: str) -> str:
    normalized = raw.strip().lower().lstrip("@")
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    return normalized or "resident"


def _profile_link(handle: str) -> str:
    return {
        "alina": "profile-alina.erza",
        "noor": "profile-noor.erza",
    }.get(handle, "index.erza")


def _thread_link(slug: str) -> str:
    return {
        "launch-week": "thread-launch.erza",
        "pattern-language": "thread-patterns.erza",
        "render-path": "manifesto.erza",
    }.get(slug, "index.erza")


def _set_status(message: str) -> None:
    session()["ui_status"] = message


def _status() -> str:
    return session().get(
        "ui_status",
        "Koinonia is now backed by Supabase. Local actions and forms persist outside the runtime process.",
    )


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
    rows = _rows(
        "profiles",
        query={
            "select": "display_name,handle,bio,primary_circle,followers,following",
            "order": "followers.desc",
            "limit": "3",
        },
    )
    return [
        {
            "name": str(row["display_name"]),
            "handle": str(row["handle"]),
            "bio": str(row["bio"]),
            "primary_circle": str(row["primary_circle"]),
            "following": bool(row["following"]),
            "follow_action_label": "Unfollow" if bool(row["following"]) else "Follow",
            "profile_link": _profile_link(str(row["handle"])),
        }
        for row in rows
    ]


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
    profile = _one(
        "profiles",
        query={
            "select": "display_name,handle,bio,primary_circle,followers,following",
            "handle": f"eq.{normalized}",
        },
    )
    if profile is None:
        return {
            "name": "Unknown resident",
            "handle": normalized,
            "bio": "This profile has not been authored yet.",
            "primary_circle": "unassigned",
            "followers": 0,
            "following": False,
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
    return {
        "name": str(profile["display_name"]),
        "handle": str(profile["handle"]),
        "bio": str(profile["bio"]),
        "primary_circle": str(profile["primary_circle"]),
        "followers": int(profile["followers"]),
        "following": bool(profile["following"]),
        "follow_action_label": "Unfollow builder" if bool(profile["following"]) else "Follow builder",
        "posts": [_post_card(post) for post in posts],
    }


@handler("mission.highlights")
def mission_highlights() -> list[dict[str, str]]:
    return [
        {
            "title": "Terminal-native first",
            "body": "Keep the social loop readable through sections, text, links, actions, and forms instead of web chrome.",
        },
        {
            "title": "Protocol pressure",
            "body": "Use a public Render endpoint to pressure-test the erzanet path before the language gets too comfortable.",
        },
        {
            "title": "Persistent state",
            "body": "Supabase now holds posts, replies, profiles, and circles so the prototype survives process restarts.",
        },
    ]


@handler("feed.like")
def feed_like(post_id: int) -> None:
    _rpc("increment_post_like", post_id=int(post_id))
    _set_status(f"Signaled dispatch {post_id}.")


@handler("feed.boost")
def feed_boost(post_id: int) -> None:
    _rpc("increment_post_boost", post_id=int(post_id))
    _set_status(f"Boosted dispatch {post_id}.")


@handler("people.toggle_follow")
def people_toggle_follow(handle: str) -> None:
    normalized = _normalize_handle(handle)
    result = _rpc("toggle_profile_follow", profile_handle=normalized)
    state = False
    if isinstance(result, bool):
        state = result
    elif isinstance(result, str):
        state = result.lower() == "true"
    _set_status(f"{'Following' if state else 'Stopped following'} @{normalized}.")


@route("/posts")
def create_post(author: str = "", handle: str = "", body: str = ""):
    if not author.strip() or not body.strip():
        return error("Display name and dispatch are required.")
    _rpc(
        "create_dispatch",
        author_name=author.strip(),
        profile_handle=handle.strip(),
        body=body.strip(),
    )
    _set_status(f"Published a new dispatch as @{_normalize_handle(handle)}.")
    return redirect("index.erza")


@route("/threads/launch-week/reply")
def reply_launch_week(author: str = "", handle: str = "", body: str = ""):
    return _append_reply("launch-week", "thread-launch.erza", author, handle, body)


@route("/threads/pattern-language/reply")
def reply_pattern_language(author: str = "", handle: str = "", body: str = ""):
    return _append_reply("pattern-language", "thread-patterns.erza", author, handle, body)


def _append_reply(slug: str, page: str, author: str, handle: str, body: str):
    if not author.strip() or not body.strip():
        return error("Both name and reply text are required.")
    _rpc(
        "add_thread_reply",
        thread_slug=slug,
        author_name=author.strip(),
        profile_handle=handle.strip(),
        body=body.strip(),
    )
    _set_status(f"Replied to {slug}.")
    return redirect(page)
