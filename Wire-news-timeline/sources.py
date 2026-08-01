"""
Starter list of major-outlet RSS feeds, plus support for user-added custom
feeds. RSS URLs occasionally get moved/retired by the outlet itself — if a
feed in here stops returning items, check the outlet's own site for a
current RSS link and update the URL below (or just remove it and add your
own working URL from Settings, same as any custom feed).
"""

# key -> (display name, RSS url)
STARTER_SOURCES = {
    "cnn": ("CNN - Top Stories", "http://rss.cnn.com/rss/cnn_topstories.rss"),
    "cbc": ("CBC News - Top Stories", "https://www.cbc.ca/webfeed/rss/rss-topstories"),
    "bbc": ("BBC News - World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    "nbc": ("NBC News", "http://feeds.nbcnews.com/nbcnews/public/news"),
    "foxnews": ("Fox News - Latest", "http://feeds.foxnews.com/foxnews/latest"),
    "nytimes": ("NY Times - Home Page", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    "npr": ("NPR - News", "https://feeds.npr.org/1001/rss.xml"),
    "guardian": ("The Guardian - World", "https://www.theguardian.com/world/rss"),
    "aljazeera": ("Al Jazeera - All News", "https://www.aljazeera.com/xml/rss/all.xml"),
    "apnews": ("AP News - Top Headlines", "https://apnews.com/apf-topnews?format=rss"),
    "reuters": ("Reuters - World", "https://www.reutersagency.com/feed/?best-topics=world&post_type=best"),
    "cbsnews": ("CBS News", "https://www.cbsnews.com/latest/rss/main"),
    "abcnews": ("ABC News - Top Stories", "https://abcnews.go.com/abcnews/topstories"),
    "skynews": ("Sky News - Home", "https://feeds.skynews.com/feeds/rss/home.xml"),
    "wsj_world": ("WSJ - World News", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
}
