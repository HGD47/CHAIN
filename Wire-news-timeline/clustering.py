"""
Groups articles from different sources together when they're clearly
covering the same event (e.g. CNN and NBC both running a headline about
the same wildfire) so the timeline shows one stacked "event" card instead
of a dozen near-duplicate rows.

This is a lightweight, dependency-free approach (no ML libraries, so it
stays easy to bundle with PyInstaller): headlines are reduced to a set of
meaningful words, and two articles are considered the same event if that
word overlap (Jaccard similarity) clears a threshold AND they were
published within a configurable time window of each other. It's a
heuristic, not perfect — very short or very generic headlines ("Senate
votes today") can under- or over-cluster. `cluster_threshold` in Settings
lets you tune how strict the matching is.
"""
import re
import hashlib

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or",
    "but", "is", "are", "was", "were", "be", "been", "being", "as", "by",
    "with", "from", "that", "this", "it", "its", "his", "her", "their",
    "after", "over", "into", "amid", "amidst", "than", "then", "will",
    "has", "have", "had", "says", "said", "says:", "new", "up", "out",
    "about", "us", "u.s", "u.s.",
}

_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokenize(title: str) -> set:
    words = _WORD_RE.findall(title.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _similarity(tokens_a: set, tokens_b: set) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union else 0.0


def _stable_event_id(anchor_article: dict) -> str:
    """A content-based id (hash of the earliest article's link, or its
    title if a feed didn't provide one) instead of a positional index.
    This matters because the whole article store gets reclustered from
    scratch on every refresh — a positional id like "evt_3" would point
    at a different story every time, breaking hide/unhide and "seen it"
    tracking. Hashing the earliest article is stable as long as that
    article stays the earliest one in its cluster, which holds true the
    vast majority of the time in practice."""
    basis = anchor_article.get("link") or anchor_article.get("title", "")
    return "evt_" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def cluster_articles(articles: list, threshold: float = 0.42, window_hours: float = 36) -> list:
    """Returns a list of event dicts, newest first:
    {
        "id": str,                # stable content-based id, see _stable_event_id
        "headline": str,          # headline of the earliest article in the cluster
        "first_seen": iso str,
        "first_seen_ts": float,
        "last_seen": iso str,
        "last_seen_ts": float,
        "sources": [source names, deduped, in order first reported],
        "articles": [article dicts, oldest first],
    }
    """
    window_seconds = window_hours * 3600
    ordered = sorted(articles, key=lambda a: a["published_ts"])

    events = []  # each: {"tokens": set, "articles": [...], "anchor_ts": float}

    for art in ordered:
        tokens = _tokenize(art["title"])
        art["_tokens"] = tokens

        best_event = None
        best_score = 0.0
        for ev in events:
            if abs(art["published_ts"] - ev["anchor_ts"]) > window_seconds:
                continue
            score = _similarity(tokens, ev["tokens"])
            if score > best_score:
                best_score = score
                best_event = ev

        if best_event is not None and best_score >= threshold:
            best_event["articles"].append(art)
            best_event["tokens"] = best_event["tokens"] | tokens
            best_event["anchor_ts"] = art["published_ts"]
        else:
            events.append({
                "tokens": tokens,
                "articles": [art],
                "anchor_ts": art["published_ts"],
            })

    result = []
    for ev in events:
        arts = ev["articles"]
        seen_sources = []
        for a in arts:
            if a["source_name"] not in seen_sources:
                seen_sources.append(a["source_name"])
            a.pop("_tokens", None)
        result.append({
            "id": _stable_event_id(arts[0]),
            "headline": arts[0]["title"],
            "first_seen": arts[0]["published"],
            "first_seen_ts": arts[0]["published_ts"],
            "last_seen": arts[-1]["published"],
            "last_seen_ts": arts[-1]["published_ts"],
            "sources": seen_sources,
            "source_count": len(seen_sources),
            "articles": list(reversed(arts)),  # newest article of the event first
        })

    result.sort(key=lambda e: e["last_seen_ts"], reverse=True)
    return result
