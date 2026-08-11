"""
Pulls articles out of each enabled RSS feed and normalizes them into a
plain dict shape the rest of the app can work with, regardless of which
particular RSS fields that outlet happens to fill in.
"""
from datetime import datetime, timezone
from calendar import timegm

import feedparser
import requests

REQUEST_TIMEOUT = 15  # seconds

# Some outlets quietly block or rate-limit requests that don't look like
# a real browser (feedparser's default User-Agent is an easy tell) — a
# realistic one here fixes a chunk of "connection failed" style errors
# that are actually silent blocking, not a real network problem.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


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


def _get_with_retry(url: str, attempts: int = 2):
    """One retry for transient failures (a single dropped connection
    shouldn't count as a dead source) — but SSL and HTTP errors aren't
    retried since trying again won't fix those. (SSLError is technically
    a subclass of ConnectionError in requests, so it's checked first and
    re-raised immediately rather than falling into the retry loop.)"""
    last_exc = None
    for attempt in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.SSLError:
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exc = e
            continue
    raise last_exc


def fetch_source(name: str, url: str, key: str) -> list:
    """Fetch one feed. Returns a list of article dicts. Raises FeedError
    on total failure (feed unreachable / not parseable) so the caller can
    show a per-source warning instead of the whole refresh failing.

    Uses `requests` with an explicit timeout and a browser User-Agent
    rather than handing the URL straight to feedparser — feedparser's
    own fetch has no timeout by default, so a slow or unresponsive
    server can hang far longer than is reasonable before finally
    surfacing as a raw OS-level error (e.g. Windows' WinError 10060)
    instead of a clear message. A single dropped connection gets one
    automatic retry before it's treated as a real failure."""
    try:
        resp = _get_with_retry(url)
    except requests.exceptions.Timeout:
        raise FeedError(f"Timed out after {REQUEST_TIMEOUT}s (tried twice) — the site may be slow, blocking automated requests, or down.")
    except requests.exceptions.SSLError as e:
        raise FeedError(f"SSL/certificate error: {e}")
    except requests.exceptions.ConnectionError:
        raise FeedError("Couldn't connect after two tries — check your internet connection, or the site may be down.")
    except requests.exceptions.HTTPError as e:
        raise FeedError(f"Server returned an error: {e}")
    except requests.exceptions.RequestException as e:
        raise FeedError(str(e))

    parsed = feedparser.parse(resp.content)

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
