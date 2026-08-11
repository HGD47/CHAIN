"""
Definitions for the Regions feature: the supported countries and
supra-national groupings, the keywords used to auto-tag articles, and
the descriptions/maps shown on each region's page.

Tagging is a lightweight heuristic (word-boundary keyword matching
against an article's title + summary), not a real geocoding/NLP system —
it will occasionally mis-tag (e.g. an article that mentions "Mexico" only
in passing) or miss articles that refer to a place without naming it
directly. Multiple regions can match the same article; it'll show up in
every region tab it matches.

Map images (static/maps/<key>.svg) are derived from "Simple World Map"
by Al MacDonald, edited by Fritz Lekschas, CC BY-SA 3.0
(https://github.com/flekschas/simple-world-map) — cropped, dimmed/
highlighted, and recolored per region.
"""
import re

REGION_DEFS = {
    "canada": {
        "label": "Canada",
        "is_country": True,
        "keywords": ["canada", "canadian"],
        "description": (
            "A federal parliamentary democracy of ten provinces and three territories, "
            "Canada is the world's second-largest country by area but one of the most "
            "urbanized, with most of its population concentrated within roughly 150 miles "
            "of the US border. It's a constitutional monarchy under the Canadian Crown, "
            "governed day-to-day by a Prime Minister and Parliament in Ottawa. Quebec's "
            "distinct French-speaking majority and long-running sovereignty debate remain "
            "a defining feature of national politics, alongside Indigenous rights and land "
            "claims across the country."
        ),
    },
    "usa": {
        "label": "United States",
        "is_country": True,
        "keywords": ["united states", "u.s.", "usa", "u.s.a"],
        "description": (
            "A federal republic of 50 states plus DC and several territories, built on a "
            "separation of powers between an elected President, a bicameral Congress, and "
            "an independent judiciary. Its two-party system (Democratic and Republican) "
            "dominates federal politics, while significant policy authority — including "
            "elections themselves — sits with individual states. As the world's largest "
            "economy and a permanent UN Security Council member, US domestic politics and "
            "foreign policy both carry outsized global weight."
        ),
    },
    "spain": {
        "label": "Spain",
        "is_country": True,
        "keywords": ["spain", "spanish"],
        "description": (
            "A parliamentary constitutional monarchy in southwestern Europe, Spain is "
            "organized into 17 autonomous communities with varying degrees of devolved "
            "power — most notably Catalonia and the Basque Country, both home to active "
            "independence or greater-autonomy movements. A member of the EU, NATO, and the "
            "eurozone since the 1980s–90s, Spain transitioned from the Franco dictatorship "
            "to democracy in the late 1970s, a history that still shapes its politics today."
        ),
    },
    "uk": {
        "label": "United Kingdom",
        "is_country": True,
        "keywords": ["united kingdom", "u.k.", "britain", "british"],
        "description": (
            "A constitutional monarchy and parliamentary democracy made up of England, "
            "Scotland, Wales, and Northern Ireland, each with differing levels of devolved "
            "government. The UK left the European Union in 2020 (\"Brexit\") after a 2016 "
            "referendum, a decision whose economic and political fallout remains a live "
            "issue. Scottish independence and Northern Ireland's post-Brexit trading "
            "arrangements are two of the most consistently contentious internal fault lines."
        ),
    },
    "mexico": {
        "label": "Mexico",
        "is_country": True,
        "keywords": ["mexico", "mexican"],
        "description": (
            "A federal presidential republic of 31 states plus Mexico City, Mexico is "
            "Latin America's second-largest economy and deeply linked to the US through "
            "trade (via the USMCA agreement), migration, and a long shared border. Domestic "
            "politics has been dominated in recent years by the Morena party, and organized-"
            "crime violence and cartel-linked corruption remain central, ongoing challenges "
            "for governance and security policy."
        ),
    },
    "eu": {
        "label": "European Union",
        "display": "EU",
        "is_country": False,
        "keywords": [r"european union", r"\beu\b"],
        "description": (
            "A political and economic union of 27 member states across Europe, the EU "
            "operates through a mix of supranational institutions (the European Commission, "
            "Parliament, and Court of Justice) and intergovernmental ones (the European "
            "Council, made up of member states' own leaders). Most, but not all, members "
            "share the euro currency and the Schengen open-border area. Enlargement "
            "(candidate countries seeking to join), migration policy, and member states' "
            "diverging positions on major foreign-policy questions are recurring themes."
        ),
    },
    "europe": {
        "label": "Europe",
        "display": "Europe",
        "is_country": False,
        "keywords": ["europe", "european"],
        "description": (
            "A continent of roughly 40+ sovereign states spanning far more political "
            "variety than the EU alone — including non-EU members like the UK, Norway, "
            "Switzerland, and the Balkan and Caucasus states, several of which are EU "
            "candidate countries. Post-Soviet realignment, NATO's eastward expansion, and "
            "the war in Ukraine have kept European security arrangements in significant "
            "flux since 2022."
        ),
    },
    "north_america": {
        "label": "North America",
        "display": "NA",
        "is_country": False,
        "keywords": ["north america", "north american"],
        "description": (
            "The continent spanning Canada and the US in the north through Mexico and "
            "Central America and into the Caribbean. Economically integrated to varying "
            "degrees through agreements like the USMCA, the region's politics are shaped "
            "heavily by migration patterns — both northward toward the US/Canada and "
            "regionally within Central America — as well as by drug-trafficking routes "
            "and the security policy built around them."
        ),
    },
    "south_america": {
        "label": "South America",
        "display": "SA",
        "is_country": False,
        "keywords": ["south america", "south american", "latin america", "latin american"],
        "description": (
            "A continent of 12 countries, most governed as presidential republics and "
            "nearly all former Spanish or Portuguese colonies (Brazil being the major "
            "Portuguese-speaking exception). Regional politics has swung between left- and "
            "right-leaning governments across different countries in recent election "
            "cycles, and cross-border issues — Amazon deforestation, Venezuelan migration, "
            "and commodity-driven economies — feature heavily in coverage of the region."
        ),
    },
    "africa": {
        "label": "Africa",
        "display": "AF",
        "is_country": False,
        "keywords": ["africa", "african"],
        "description": (
            "The world's second-largest and second-most-populous continent, home to 54 "
            "recognized countries with enormous variation in political systems, languages, "
            "and economies — from long-established democracies to recent coups (several in "
            "the Sahel region in the 2020s) to resource-driven economies navigating foreign "
            "investment from multiple global powers. The African Union is the continent's "
            "primary political and economic bloc, broadly analogous in aim to the EU."
        ),
    },
    "asia": {
        "label": "Asia",
        "display": "AS",
        "is_country": False,
        "keywords": ["asia", "asian"],
        "description": (
            "The world's largest and most populous continent by a wide margin, spanning "
            "political systems from parliamentary democracies to one-party states to "
            "absolute monarchies. Coverage of the region is dominated by a handful of "
            "major storylines: US-China strategic competition, tensions on the Korean "
            "peninsula and across the Taiwan Strait, India's and Southeast Asia's rapid "
            "economic growth, and the ongoing conflicts and diplomacy across the Middle East."
        ),
    },
    "nato": {
        "label": "NATO",
        "display": "NATO",
        "is_country": False,
        "keywords": ["nato", "north atlantic treaty"],
        "description": (
            "A 32-member military alliance built around Article 5's collective-defense "
            "commitment — an attack on one member is treated as an attack on all. Formed "
            "in 1949 as a Cold War counterweight, NATO expanded significantly after 2022 "
            "with Finland and Sweden's accession in response to Russia's invasion of "
            "Ukraine. Member states' defense-spending commitments and the alliance's role "
            "in supporting Ukraine are recurring points of internal debate."
        ),
    },
}


def tag_regions(article: dict) -> list:
    """Returns the list of region keys whose keywords appear in this
    article's title or summary, word-boundary matched (case-insensitive)
    so short tokens like "eu" don't match inside unrelated words."""
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    matched = []
    for key, info in REGION_DEFS.items():
        for kw in info["keywords"]:
            if kw.startswith(r"\b") or "\\b" in kw:
                pattern = kw
            else:
                pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text):
                matched.append(key)
                break
    return matched
