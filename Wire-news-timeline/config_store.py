"""
Local JSON files that hold everything between runs:

- config.json     -> which sources are enabled, custom feeds, tuning
                      knobs, and when you last viewed the timeline
- articles.json   -> every article ever pulled (deduped by link), so the
                      timeline builds up a real history instead of only
                      showing whatever came back on the last refresh
- cache.json      -> the clustered events computed from articles.json,
                      so the timeline page loads instantly without
                      reclustering on every request
- dismissed.json  -> ids of events you've hidden from the main timeline
- timelines.json  -> your saved custom timelines (name + a snapshot of
                      whichever stories you added to each one)

This app is meant to run on your own machine only.
"""
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
CACHE_PATH = os.path.join(_DATA_DIR, "cache.json")
ARTICLES_PATH = os.path.join(_DATA_DIR, "articles.json")
DISMISSED_PATH = os.path.join(_DATA_DIR, "dismissed.json")
TIMELINES_PATH = os.path.join(_DATA_DIR, "timelines.json")

DEFAULTS = {
    # starter sources default to OFF so you consciously pick your outlets
    "enabled_starter": [],
    # list of {"name": str, "url": str} dicts the user typed in themselves
    "custom_sources": [],
    # how close two headlines need to be (0-1) to stack as the same event
    "cluster_threshold": 0.42,
    # only cluster articles published within this many hours of each other
    "cluster_window_hours": 36,
    # how many days of history to keep around before an article is pruned
    # from the local store (keeps articles.json from growing forever)
    "retention_days": 45,
    # unix timestamp of the last time the timeline was opened; used to
    # figure out which events are "new since you last checked"
    "last_viewed_ts": 0,
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        # A brand new install: nothing has ever been pulled, so there's
        # nothing to flag as "new" yet. Stamping last_viewed_ts as "now"
        # (instead of 0 / the dawn of time) means the very first pull you
        # ever do won't light up every single event as NEW.
        data = dict(DEFAULTS)
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
    """Returns a flat list of {"key", "name", "url"} for every source
    currently turned on (starter outlets picked + all custom feeds)."""
    active = []
    for key in config.get("enabled_starter", []):
        if key in STARTER_SOURCES:
            name, url = STARTER_SOURCES[key]
            active.append({"key": key, "name": name, "url": url})
    for i, src in enumerate(config.get("custom_sources", [])):
        active.append({"key": f"custom_{i}", "name": src["name"], "url": src["url"]})
    return active


def load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {"last_run": None, "events": [], "errors": []}
    with open(CACHE_PATH, "r") as f:
        return json.load(f)


def save_cache(data: dict) -> None:
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ---------- Persistent article store ----------

def load_articles() -> list:
    """All articles ever pulled, deduped by link. This is the source of
    truth the timeline is built from — cache.json is just a precomputed
    view of this for fast page loads."""
    if not os.path.exists(ARTICLES_PATH):
        return []
    with open(ARTICLES_PATH, "r") as f:
        return json.load(f)


def save_articles(articles: list) -> None:
    with open(ARTICLES_PATH, "w") as f:
        json.dump(articles, f, indent=2)


def merge_articles(existing: list, new_articles: list, retention_days: float = 45) -> tuple:
    """Adds any genuinely new articles (by link, falling back to
    source+title for the rare item with no link) into the existing store,
    and drops anything older than retention_days so the file doesn't grow
    forever. Existing articles are left untouched — this never rewrites
    history, only adds to it and prunes the oldest edge.
    Returns (merged_list, count_added)."""
    seen_keys = set()
    merged = []

    def key_for(a):
        return a.get("link") or f"{a.get('source_key')}::{a.get('title')}"

    cutoff_ts = time.time() - (retention_days * 86400)

    for a in existing:
        k = key_for(a)
        if a.get("published_ts", 0) < cutoff_ts:
            continue
        if k in seen_keys:
            continue
        seen_keys.add(k)
        merged.append(a)

    added = 0
    for a in new_articles:
        k = key_for(a)
        if k in seen_keys:
            continue
        if a.get("published_ts", 0) < cutoff_ts:
            continue
        seen_keys.add(k)
        merged.append(a)
        added += 1

    return merged, added


# ---------- Dismissed / hidden events ----------

def load_dismissed() -> set:
    if not os.path.exists(DISMISSED_PATH):
        return set()
    with open(DISMISSED_PATH, "r") as f:
        return set(json.load(f))


def save_dismissed(dismissed_ids) -> None:
    with open(DISMISSED_PATH, "w") as f:
        json.dump(sorted(dismissed_ids), f, indent=2)


# ---------- Custom timelines ----------

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
    """Adds a story snapshot to a timeline, deduped by link.
    Returns True if it was actually added (False if already present)."""
    existing_links = {s.get("link") for s in timeline["stories"] if s.get("link")}
    if story.get("link") and story["link"] in existing_links:
        return False
    timeline["stories"].append(story)
    return True
