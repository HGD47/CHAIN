"""
Matches articles against a "word-catch" rule attached to a custom
timeline, so the timeline can auto-fill with anything matching a set of
required keywords — either all in the same article, or spread across
different articles published within a rolling time window of each other.

This is a heuristic, not a precise search engine. In particular, the
cross-article mode's "does this cluster cover every keyword" check uses
a simple forward sliding window per candidate start article rather than
an exhaustive search over every possible grouping — fast enough for a
personal article store, and easy to reason about, at the cost of
occasionally pulling in a slightly wider group than the tightest
possible match.
"""

MAX_KEYWORDS = 4


def _searchable_text(article: dict, use_body: bool) -> str:
    parts = [article.get("title", ""), article.get("summary", "")]
    if use_body and article.get("body_text"):
        parts.append(article["body_text"])
    return " ".join(parts).lower()


def _clean_keywords(keywords: list) -> list:
    return [k.strip() for k in (keywords or []) if k and k.strip()][:MAX_KEYWORDS]


def find_matches(rule: dict, articles: list) -> list:
    """Returns the list of article dicts that satisfy the rule."""
    keywords = _clean_keywords(rule.get("keywords"))
    if not keywords:
        return []

    use_body = bool(rule.get("search_body"))
    mode = rule.get("mode", "same_article")
    lowered_keywords = [k.lower() for k in keywords]

    if mode == "same_article":
        matches = []
        for a in articles:
            text = _searchable_text(a, use_body)
            if all(k in text for k in lowered_keywords):
                matches.append(a)
        return matches

    # cross_article mode: each keyword can come from a different article,
    # as long as the whole group falls within window_days of each other.
    window_seconds = max(1, rule.get("window_days", 21)) * 86400

    tagged = []
    for a in articles:
        text = _searchable_text(a, use_body)
        found = {k for k in lowered_keywords if k in text}
        if found:
            tagged.append((a, found))
    tagged.sort(key=lambda pair: pair[0]["published_ts"])

    required = set(lowered_keywords)
    result_ids = set()
    result = []
    n = len(tagged)
    for i in range(n):
        base_ts = tagged[i][0]["published_ts"]
        group = []
        covered = set()
        for j in range(i, n):
            article_j, kws_j = tagged[j]
            if article_j["published_ts"] - base_ts > window_seconds:
                break
            group.append(article_j)
            covered |= kws_j
        if covered == required:
            for article_j in group:
                if article_j["id"] not in result_ids:
                    result_ids.add(article_j["id"])
                    result.append(article_j)

    return result
