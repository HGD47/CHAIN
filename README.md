# Wire — a local news timeline

A local web app that pulls RSS feeds from whichever news outlets you pick
and lays them out as a timeline, newest first. Runs entirely on your
machine. Nothing is sent anywhere except the direct requests to each RSS
feed you enable.

## What's new in this version

- **Word-catch rules on Your Timelines** — up to 4 keywords, with a
  choice of matching mode: **all keywords in the same article**, or
  **keywords across different articles, published within N days of each
  other**. New matches get added automatically on every pull, plus a
  "Check for matches now" button. Optional "also search full article
  text" (not just headline/summary) — off by default since it fetches
  each candidate's actual page, which is slower and occasionally fails
  on sites that block bots; capped at 25 fetches per check either way.
- **Fixed:** the Rename box on a timeline's page was cramped into a
  30px-tall button clipped to a fixed icon-button size — now sized
  correctly.
- **Quieter console** — per-request log spam is suppressed. On Windows,
  a button in the header lets you hide/show the command-prompt window
  entirely (no extra install — uses Windows' own API via Python's
  built-in `ctypes`). Not available on Mac/Linux; there's no equivalent
  cross-platform way to do this without extra dependencies.
- **Auto-close the browser tab when Wire stops** — whether that's from
  the Stop button, closing the console/terminal window, or the process
  being killed any other way, the browser tab tries to close itself.
  Browsers only allow this for tabs opened by a script (which is how
  Wire's launcher opens its tab) — but some browsers block it regardless
  as a hard rule with no exception, so treat it as best-effort, not a
  guarantee; the tab will always tell you it's safe to close manually
  either way.

**Big structural change: automatic story-stacking is gone.** The
Timeline is now a flat, one-row-per-article list — every article from
every enabled source, on its own. If you want to group stories about the
same event together, do it manually on **Your Timelines** by adding them
there yourself (drag-to-position/reorder is a planned follow-up, not in
yet).

- **Select mode** — a "Select stories" button on the Timeline lets you
  check several stories at once and add them all to one custom timeline
  in a single action, instead of one at a time.
- **Notifications tab** — system messages only (source errors on a pull,
  storage warnings) — separate from your news. Clear them individually
  or all at once.
- **Sources / Settings split** — **Sources** is now where you pick
  outlets AND read about each one (political leaning, ownership,
  credibility notes, sourced from AllSides/Ad Fontes-style bias-rating
  conventions — see the disclaimer on that page). **Settings** now only
  holds tuning: retention, automatic pulls, and storage.
- **Optional automatic pulls** — off by default. Turning it on in
  Settings pulls on a timer while Wire is open, which helps catch
  stories that would otherwise scroll off a fast outlet's feed between
  your visits. It can't retrieve anything from while your computer was
  off or the app was closed — there's no way around that with RSS.
- **Storage warning** — Settings shows how much disk space your saved
  history is using, with an optional slider to get warned (via
  Notifications) once it crosses a size you set. Unlimited by default;
  nothing is ever auto-deleted.
- **Print / Save as PDF** — every custom timeline has a print button
  that uses your browser's built-in print-to-PDF, formatted cleanly with
  buttons and nav hidden.
- Search bar, source filter, and sort menu; light mode; a Stop button;
  browser tab favicon; renamed to "Your Timelines"; timelines are
  rename-able. (Carried over from the previous version.)

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

This app does **not** auto-refresh in the background by default — hit
**Pull latest** on the Timeline page whenever you want an update. You
can turn on optional automatic pulls in Settings if you'd rather it keep
itself topped up while it's open.

Each pull fetches every enabled feed and merges any genuinely new
articles into a running local history (`articles.json`) — nothing is
grouped or stacked automatically; every article gets its own row on the
Timeline, newest first, with a timestamp on the left (exact date/time on
top, relative time below).

## Hiding a story

Every story has a small **✕** button. Hiding one only removes that
single article — it doesn't touch anything else from the same outlet, so
one bad story doesn't cost you the rest of that source's coverage. A
"Show N hidden stories" link appears above the timeline whenever you've
hidden anything, and each hidden row has a **↺** button to bring it back.

## Search, filter, sort, and Select mode

The search bar filters by keyword (headline + summary text), the
dropdown narrows to one source, and the sort menu covers newest/oldest,
headline A–Z/Z–A, and source A–Z/Z–A. **Select stories** turns on a
checkbox next to every row so you can add several at once to a custom
timeline in one action, instead of one at a time.

## New-since-you-checked

Opening the Timeline page marks everything as seen. Anything that showed
up since your last visit gets a small `NEW` tag under its timestamp, and
the **Timeline** nav item shows a count badge for how many are waiting.

## Notifications

System messages only — source errors from a pull, storage warnings —
live on their own **Notifications** tab, separate from your news. Clear
them one at a time or all at once; the nav badge shows how many are
still active.

## Your Timelines

A separate space for building a focused timeline around one story or
topic. On any story on the main feed, open **"+ Add to a custom
timeline"** (or use **Select mode** to add several at once) and either
pick an existing timeline or type a new name. Custom timelines are:

- **Saved to disk** (`timelines.json`) — there whenever you come back,
  independent of the main article history/retention window.
- **Sorted chronologically**, oldest to newest, by when the story was
  originally published.
- **Editable** — rename from the detail page, remove any story with its
  own ✕, or delete the whole timeline.
- **Printable** — the "Print / Save as PDF" button uses your browser's
  built-in print dialog, formatted cleanly with nav/buttons hidden.

## History & storage

Every pull adds to a persistent local store instead of replacing it — an
article you've already seen (by link) is simply skipped on future pulls.
Kept for **45 days** by default before being pruned, adjustable in
**Settings**. Settings also shows how much disk space your saved history
is using, with an optional slider to get warned (via Notifications) once
it crosses a size you choose — nothing is ever auto-deleted; lower the
retention days to actually free up space.

## Automatic pulls (optional, off by default)

Turning this on in Settings pulls on a timer while Wire is left running,
which helps catch stories that would otherwise scroll off a fast-moving
outlet's live feed between your visits. It can only run while the app
process itself is open on your machine — it can't retrieve anything from
while your computer was off or Wire was closed; RSS feeds only expose an
outlet's most recent items, so there's no way to fully close that gap
after the fact.

## Files

- `app.py` — Flask routes: timeline, hide/unhide, select mode, custom
  timelines, notifications, sources, settings, manual + automatic pulls
- `sources.py` — the starter outlet list (name + RSS URL) plus the
  leaning/ownership/credibility notes shown on the Sources page
- `fetcher.py` — fetches and normalizes each RSS feed
- `config_store.py` — all local JSON persistence: `config.json` (sources,
  tuning, pull bookkeeping), `articles.json` (full article history —
  this **is** the timeline now), `dismissed.json` (hidden article ids),
  `timelines.json` (your saved custom timelines), `notifications.json`
  (system messages) — all created next to the app on first use
- `templates/`, `static/style.css` — the UI

## Adding a source permanently to the starter list

Edit the `STARTER_SOURCES` dict in `sources.py` — it's just
`key: (display name, RSS url)`. Add matching leaning/ownership/
credibility notes to `SOURCE_INFO` if you want it to show up on the
Sources page too. No code changes needed elsewhere.

