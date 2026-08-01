# Wire — a local news timeline

A local web app that pulls RSS feeds from whichever news outlets you pick,
and lays them out as a timeline. When two or more outlets are clearly
covering the same story (e.g. CNN and NBC both reporting on the same
wildfire), it stacks them into a single event card instead of showing you
the same story five times.

Runs entirely on your machine. Nothing is sent anywhere except the direct
requests to each RSS feed you enable.

## 1. Run it

**Windows:** double-click `launch_windows.bat`
**Mac:** double-click `launch_mac.command`
  (first time only: right-click → Open, to get past Gatekeeper's
  "unidentified developer" warning)
**Linux:** run `./launch_linux.sh`

First run sets up a private virtual environment and installs dependencies
(~20-30s). Every run after that starts instantly and opens your browser to
**http://localhost:8765**.

Or manually:
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## 2. Pick your sources

Go to the **Sources** tab. There's a starter list of ~14 major outlets
(CNN, BBC, NBC, Fox, NYT, NPR, Guardian, Al Jazeera, AP, Reuters, CBS,
ABC, Sky News, WSJ) — check the boxes for whichever ones you want. You
can also add any outlet with a public RSS URL under **Custom feeds** —
local papers, trade press, blogs, anything.

**A heads-up on the starter list:** outlets move or retire their RSS URLs
without much notice, and I put these together from what's publicly
documented rather than testing every single one live. If a source shows
up as an error after you pull the wire, that almost always means its RSS
URL has changed — search "[outlet name] RSS feed" to find the current
one and swap it in (remove the broken starter one's checkbox, add the
working URL as a custom feed instead).

## 3. Pull the wire

This app does **not** auto-refresh in the background — hit **Pull latest**
on the Timeline page whenever you want an update. That's a deliberate
choice: it means it's not silently hammering news sites' servers on a
timer while your laptop is open.

Each pull fetches every enabled feed, merges any genuinely new articles
into a running local history (`articles.json`), then groups same-story
articles together and shows the newest events first — with a timestamp
on the left of every story (exact date/time on top, relative time below).

## Hiding a story

Every event card has a small **✕** button. Hiding an event only removes
that one story — it doesn't touch anything else from the same outlet, so
one bad match doesn't cost you the rest of that source's coverage. A
"Show N hidden events" link appears above the timeline whenever you've
hidden anything, and each hidden card has a **↺** button to bring it
back.

## New-since-you-checked

Opening the Timeline page marks everything as seen. Anything that showed
up since your last visit gets a small `NEW` tag under its timestamp, and
the **Timeline** nav item shows a count badge for how many are waiting.
There's no separate notifications page anymore — it's all just the one
timeline.

## Custom timelines

The **Custom Timelines** tab is a separate space for building a focused
timeline around one story or topic. On any event card on the main feed,
open **"+ Add to a custom timeline"** and either pick an existing
timeline from the dropdown or type a new name — either adds that story,
snapshotted as-is, to that timeline. Custom timelines are:

- **Saved to disk** (`timelines.json`) — they're there whenever you come
  back, independent of the main article history/retention window.
- **Sorted chronologically**, oldest to newest, by when the story was
  originally published — so opening one reads like the actual timeline
  of how a story developed.
- **Editable** — remove any story with its own ✕ button, or delete the
  whole timeline from its detail page.

## History

Every pull adds to a persistent local store instead of replacing it, so
the timeline builds up real history across sessions rather than only
ever showing whatever came back on the most recent pull. Two article
merges never overwrite each other — a link you've already seen is simply
skipped, and everything gets reclustered from the full stored history
each time.

By default articles are kept for **45 days** before being quietly pruned
(so `articles.json` doesn't grow forever) — adjustable from
**Sources → History**.

## How the stacking works

Two articles get stacked into the same event if:
1. They were published within `cluster_window_hours` of each other
   (36 hours by default), **and**
2. Their headlines share enough distinct words to clear the
   `cluster_threshold` similarity score (0.42 by default, on a 0-1 scale).

This is a lightweight word-overlap heuristic (no ML libraries), tunable
from **Sources → Stacking sensitivity**:
- Raise the threshold if unrelated stories are getting grouped together.
- Lower it if the same story from different outlets isn't stacking.

It isn't perfect — very short or very generic headlines ("Senate votes
today") can under- or over-match. Click "N articles on this story" on any
event card to see exactly which articles got grouped, so you can tell if
the threshold needs adjusting.

## Files

- `app.py` — Flask routes (timeline, hide/unhide, custom timelines, settings, manual refresh)
- `sources.py` — the starter outlet list (name + RSS URL)
- `fetcher.py` — fetches and normalizes each RSS feed
- `clustering.py` — groups articles into stacked events, with stable
  content-based event IDs so hiding/unhiding survives reclustering
- `config_store.py` — all local JSON persistence: `config.json` (sources,
  tuning), `articles.json` (full article history), `cache.json`
  (precomputed timeline), `dismissed.json` (hidden event ids),
  `timelines.json` (your saved custom timelines) — all created next to
  the app on first use
- `templates/`, `static/style.css` — the UI

## Adding a source permanently to the starter list

Edit the `STARTER_SOURCES` dict in `sources.py` — it's just
`key: (display name, RSS url)`. No code changes needed elsewhere.

## Authors Note
-made by a free claude subscription
-barely works
-published so i could give it to friends
-if u like it use it
-ive found it very helpful tbh