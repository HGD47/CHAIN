"""
Pulls articles out of each enabled RSS feed and normalizes them into a
plain dict shape the rest of the app can work with, regardless of which
particular RSS fields that outlet happens to fill in.
"""
from datetime import datetime, timezone
from calendar import timegm

import feedparser


class FeedError(Exception):
    pass


def _to_utc_datetime(entry) -> datetime:
    """feedparser gives a struct_time in *_parsed fields when it could
    parse a date; fall back to "now" if a feed omits/mangles it so the
    article still shows up rather than getting silently dropped."""
    for field in ("published_parsed", "updated_parsed"):
        t = getattr(entry, field, None)
        if t:
            return datetime.fromtimestamp(timegm(t), tz=timezone.utc)
    return datetime.now(timezone.utc)


def fetch_source(name: str, url: str, key: str) -> list:
    """Fetch one feed. Returns a list of article dicts. Raises FeedError
    on total failure (feed unreachable / not parseable) so the caller can
    show a per-source warning instead of the whole refresh failing."""
    parsed = feedparser.parse(url)

    if parsed.bozo and not parsed.entries:
        raise FeedError(str(parsed.bozo_exception))
    if not parsed.entries:
        raise FeedError("Feed returned no items.")

    articles = []
    for entry in parsed.entries:
        title = getattr(entry, "title", "").strip()
        if not title:
            continue
        link = getattr(entry, "link", "")
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        published = _to_utc_datetime(entry)
        articles.append({
            "source_key": key,
            "source_name": name,
            "title": title,
            "link": link,
            "summary": summary,
            "published": published.isoformat(),
            "published_ts": published.timestamp(),
        })
    return articles


def fetch_all(active_sources: list) -> tuple:
    """Fetch every enabled source. Returns (articles, errors) so a couple
    of dead feeds don't take down the whole timeline refresh."""
    articles = []
    errors = []
    for src in active_sources:
        try:
            articles.extend(fetch_source(src["name"], src["url"], src["key"]))
        except Exception as e:
            errors.append({"source": src["name"], "error": str(e)})
    return articles, errors
