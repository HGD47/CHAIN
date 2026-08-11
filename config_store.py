"""
Local JSON files that hold everything between runs:

- config.json       -> which sources are enabled, custom feeds, tuning
                        knobs, last-pull bookkeeping, auto-pull settings
- articles.json      -> every article ever pulled, deduped by link — this
                        IS the timeline now (no more clustering step)
- dismissed.json    -> ids of articles you've hidden
- timelines.json    -> your saved custom ("Your Timelines") timelines
- notifications.json -> system notices (source errors, storage warnings),
                        clearable independently of everything else

This app is meant to run on your own machine only.
"""
import hashlib
import json
import os
import sys
import time
import uuid

from sources import STARTER_SOURCES

if getattr(sys, "frozen", False):
    _DATA_DIR = os.path.dirname(sys.executable)
else:
    _DATA_DIR = os.path.dirname(__file__)

CONFIG_PATH = os.path.join(_DATA_DIR, "config.json")
ARTICLES_PATH = os.path.join(_DATA_DIR, "articles.json")
DISMISSED_PATH = os.path.join(_DATA_DIR, "dismissed.json")
TIMELINES_PATH = os.path.join(_DATA_DIR, "timelines.json")
NOTIFICATIONS_PATH = os.path.join(_DATA_DIR, "notifications.json")

DEFAULTS = {
    # starter sources default to OFF so you consciously pick your outlets
    "enabled_starter": [],
    # list of {"name": str, "url": str} dicts the user typed in themselves
    "custom_sources": [],
    # how many days of history to keep around before an article is pruned
    # from the local store (keeps articles.json from growing forever)
    "retention_days": 45,
    # unix timestamp of the last time the timeline was opened; used to
    # figure out which articles are "new since you last checked"
    "last_viewed_ts": 0,
    # "dark" or "light"
    "theme": "dark",
    # bookkeeping for the most recent pull (manual or automatic)
    "last_pull_ts": None,
    "last_pull_errors": [],
    # optional background auto-pull, off by default — only runs while
    # the app process is actually open on your machine
    "auto_pull_enabled": False,
    "auto_pull_interval_hours": 4,
    # 0 = unlimited (default). Otherwise, a warning notification fires
    # once articles.json crosses this size — nothing is auto-deleted.
    "storage_limit_mb": 0,
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        data = dict(DEFAULTS)
        # A brand new install has nothing to flag as "new" yet.
        data["last_viewed_ts"] = time.time()
        return data
    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)
    for k, v in DEFAULTS.items():
        data.setdefault(k, v)
    return data


def save_config(data: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_active_sources(config: dict) -> list:
    active = []
    for key in config.get("enabled_starter", []):
        if key in STARTER_SOURCES:
            name, url = STARTER_SOURCES[key]
            active.append({"key": key, "name": name, "url": url})
    for i, src in enumerate(config.get("custom_sources", [])):
        active.append({"key": f"custom_{i}", "name": src["name"], "url": src["url"]})
    return active


# ---------- Persistent article store (this IS the timeline now) ----------

def article_id(article: dict) -> str:
    basis = article.get("link") or article.get("title", "")
    return "art_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def load_articles() -> list:
    if not os.path.exists(ARTICLES_PATH):
        return []
    with open(ARTICLES_PATH, "r") as f:
        return json.load(f)


def save_articles(articles: list) -> None:
    with open(ARTICLES_PATH, "w") as f:
        json.dump(articles, f, indent=2)


def merge_articles(existing: list, new_articles: list, retention_days: float = 45) -> tuple:
    """Adds any genuinely new articles (deduped by link) into the store,
    stamping each with a stable id and the time it entered local storage,
    and drops anything older than retention_days. Existing entries are
    left untouched. Returns (merged_list, count_added)."""
    seen_keys = set()
    merged = []
    cutoff_ts = time.time() - (retention_days * 86400)

    def key_for(a):
        return a.get("link") or f"{a.get('source_key')}::{a.get('title')}"

    for a in existing:
        if a.get("published_ts", 0) < cutoff_ts:
            continue
        k = key_for(a)
        if k in seen_keys:
            continue
        seen_keys.add(k)
        merged.append(a)

    added = 0
    now = time.time()
    for a in new_articles:
        k = key_for(a)
        if k in seen_keys or a.get("published_ts", 0) < cutoff_ts:
            continue
        seen_keys.add(k)
        a = dict(a)
        a["id"] = article_id(a)
        a["first_stored_ts"] = now
        merged.append(a)
        added += 1

    return merged, added


def get_articles_storage_mb() -> float:
    if not os.path.exists(ARTICLES_PATH):
        return 0.0
    return round(os.path.getsize(ARTICLES_PATH) / (1024 * 1024), 2)


# ---------- Dismissed / hidden articles ----------

def load_dismissed() -> set:
    if not os.path.exists(DISMISSED_PATH):
        return set()
    with open(DISMISSED_PATH, "r") as f:
        return set(json.load(f))


def save_dismissed(dismissed_ids) -> None:
    with open(DISMISSED_PATH, "w") as f:
        json.dump(sorted(dismissed_ids), f, indent=2)


# ---------- Custom timelines ("Your Timelines") ----------

def load_timelines() -> list:
    if not os.path.exists(TIMELINES_PATH):
        return []
    with open(TIMELINES_PATH, "r") as f:
        return json.load(f)


def save_timelines(timelines: list) -> None:
    with open(TIMELINES_PATH, "w") as f:
        json.dump(timelines, f, indent=2)


def find_timeline(timelines: list, timeline_id: str):
    for t in timelines:
        if t["id"] == timeline_id:
            return t
    return None


def find_timeline_by_name(timelines: list, name: str):
    lowered = name.strip().lower()
    for t in timelines:
        if t["name"].strip().lower() == lowered:
            return t
    return None


def create_timeline(timelines: list, name: str) -> dict:
    new_timeline = {
        "id": uuid.uuid4().hex[:12],
        "name": name.strip(),
        "created_at": time.time(),
        "stories": [],
    }
    timelines.append(new_timeline)
    return new_timeline


def add_story_to_timeline(timeline: dict, story: dict) -> bool:
    existing_links = {s.get("link") for s in timeline["stories"] if s.get("link")}
    if story.get("link") and story["link"] in existing_links:
        return False
    timeline["stories"].append(story)
    return True


# ---------- System notifications (source errors, storage warnings) ----------

def load_notifications() -> list:
    if not os.path.exists(NOTIFICATIONS_PATH):
        return []
    with open(NOTIFICATIONS_PATH, "r") as f:
        return json.load(f)


def save_notifications(notifications: list) -> None:
    with open(NOTIFICATIONS_PATH, "w") as f:
        json.dump(notifications, f, indent=2)


def add_notification(notifications: list, kind: str, summary: str, details: list = None) -> dict:
    entry = {
        "id": uuid.uuid4().hex[:12],
        "kind": kind,  # "source_error" | "storage_warning"
        "summary": summary,
        "details": details or [],
        "created_at": time.time(),
        "cleared": False,
    }
    notifications.append(entry)
    return entry


def has_uncleared_of_kind(notifications: list, kind: str) -> bool:
    return any(n["kind"] == kind and not n["cleared"] for n in notifications)
