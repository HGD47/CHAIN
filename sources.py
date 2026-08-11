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
    "cbc": ("CBC News - Top Stories", "https://rss.cbc.ca/lineup/topstories.xml"),
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

# Editorial context shown on the Sources page: general political lean and
# ownership/credibility notes. Lean labels follow the AllSides Media Bias
# Chart naming convention (Left / Lean Left / Center / Lean Right / Right)
# since that's the most widely cited framework — but bias ratings differ
# by rater (AllSides, Ad Fontes Media, and Media Bias/Fact Check don't
# always agree) and are inherently contestable judgment calls, not fact.
# Ownership is more verifiable but changes with M&A — flagged below where
# a deal was pending or recent as of mid-2026.
SOURCE_INFO = {
    "cnn": {
        "leaning": "Lean Left",
        "ownership": "Warner Bros. Discovery (NYSE/Nasdaq: WBD), a publicly traded company with no single controlling owner. A Paramount Skydance acquisition of WBD was announced in 2026 and was still pending as of this writing — CNN's ownership may change.",
        "credibility": "Widely cited by fact-checking and bias-rating organizations as a mainstream, high-reach outlet; AllSides and similar raters have long placed CNN's news coverage left-of-center, distinct from its opinion programming.",
    },
    "cbc": {
        "leaning": "Lean Left",
        "ownership": "A Canadian Crown corporation — publicly funded and owned by the Government of Canada, though operationally editorially independent by law.",
        "credibility": "Canada's public broadcaster; commonly rated left-leaning by international bias charts, with government funding cited by some critics as a potential influence, though CBC operates under a legislated arm's-length mandate.",
    },
    "bbc": {
        "leaning": "Center",
        "ownership": "A UK public service broadcaster funded primarily by the mandatory TV license fee, operating under a Royal Charter rather than commercial or private ownership.",
        "credibility": "Generally rated Center by international bias charts and widely regarded as a global benchmark for broadcast journalism, though critics from multiple political directions periodically dispute this.",
    },
    "nbc": {
        "leaning": "Lean Left",
        "ownership": "NBCUniversal, a subsidiary of Comcast Corporation (Nasdaq: CMCSA).",
        "credibility": "One of the three original US broadcast networks; bias raters commonly place NBC News left-of-center, similar to its major broadcast-network peers.",
    },
    "foxnews": {
        "leaning": "Right",
        "ownership": "Fox Corporation, controlled by the Murdoch family through dual-class voting shares.",
        "credibility": "The highest-rated outlet by audience among US cable news; its news and opinion programming are rated separately by some bias charts, with opinion content generally rated further right than its straight news reporting.",
    },
    "nytimes": {
        "leaning": "Lean Left",
        "ownership": "The New York Times Company (NYSE: NYT), a public company where the Ochs-Sulzberger family retains effective control through a dual-class share structure.",
        "credibility": "A newspaper of record with one of the largest investigative and international reporting operations in US media; bias raters typically place its news pages left-of-center, with a separately rated opinion section.",
    },
    "npr": {
        "leaning": "Lean Left",
        "ownership": "A private, nonprofit membership organization; funded by member station fees, corporate sponsorships, and a small share of federal funding through the Corporation for Public Broadcasting.",
        "credibility": "Long-running public radio newsroom; most bias charts place NPR left-of-center on its news content, a rating NPR's own leadership has publicly contested at times.",
    },
    "guardian": {
        "leaning": "Left",
        "ownership": "Owned by the Scott Trust, a UK trust structure designed to preserve the paper's editorial independence without a controlling shareholder or proprietor.",
        "credibility": "A UK paper with a large international digital presence; consistently rated left-of-center, which the outlet itself doesn't dispute given its origins as a liberal paper.",
    },
    "aljazeera": {
        "leaning": "Lean Left",
        "ownership": "Funded by the government of Qatar through the Qatar Media Corporation.",
        "credibility": "State-funded but editorially separate day-to-day; critics note its state funding as a potential source of bias on stories involving Qatar or the broader Gulf region specifically, while its general international reporting is widely used by other outlets.",
    },
    "apnews": {
        "leaning": "Center",
        "ownership": "The Associated Press, a nonprofit news cooperative owned by its member newspapers and broadcasters.",
        "credibility": "A wire service whose reporting is licensed and republished by thousands of other outlets; consistently rated Center by bias charts and commonly used as a bias-neutral benchmark by researchers.",
    },
    "reuters": {
        "leaning": "Center",
        "ownership": "Thomson Reuters Corporation (TSX/Nasdaq: TRI), a public company; the Thomson family holds a controlling stake through The Woodbridge Company.",
        "credibility": "A wire service with a similar role to AP; consistently rated Center by bias charts, with a formal editorial trust principles framework governing its journalism.",
    },
    "cbsnews": {
        "leaning": "Lean Left",
        "ownership": "Paramount Skydance Corporation (Nasdaq: PSKY), formed in 2025 when Skydance Media (led by David Ellison, backed by RedBird Capital) acquired Paramount Global.",
        "credibility": "One of the three original US broadcast networks; typically rated left-of-center like its broadcast peers. Its 2025 change in ownership has drawn public scrutiny over editorial independence, including new leadership brought in from outside the network.",
    },
    "abcnews": {
        "leaning": "Lean Left",
        "ownership": "The Walt Disney Company (NYSE: DIS).",
        "credibility": "One of the three original US broadcast networks; bias raters typically place ABC News left-of-center, in line with its broadcast peers.",
    },
    "skynews": {
        "leaning": "Center",
        "ownership": "Comcast Corporation, via its Sky Group subsidiary.",
        "credibility": "UK's main commercial rolling-news broadcaster; generally rated Center by bias charts, similar to the BBC.",
    },
    "wsj_world": {
        "leaning": "Center",
        "ownership": "News Corp (Nasdaq: NWSA), controlled by the Murdoch family through dual-class voting shares — the same family that controls Fox Corporation, though the two are separate companies.",
        "credibility": "Widely regarded for financial/business reporting; bias raters commonly rate its news pages Center-to-Lean-Right, while its opinion section is rated further right and reviewed separately by most charts.",
    },
}
