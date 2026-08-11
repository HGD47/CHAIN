"""
Fetches and extracts the main body text of an article page, for rules
that opt into "search full article text" (off by default — RSS titles
and summaries are enough for most rules, and fetching every candidate's
full page is slower and occasionally fails on sites that block bots).

Results get cached onto the article record in articles.json so a given
article is only ever fetched once.
"""
import trafilatura


def fetch_body_text(url: str, timeout: int = 15) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return text or ""
    except Exception:
        return ""
