import os
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, flash

from config_store import (
    load_config, save_config, get_active_sources,
    load_cache, save_cache,
    load_articles, save_articles, merge_articles,
    load_dismissed, save_dismissed,
    load_timelines, save_timelines, find_timeline, find_timeline_by_name,
    create_timeline, add_story_to_timeline,
)
from sources import STARTER_SOURCES
from fetcher import fetch_all
from clustering import cluster_articles

if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
else:
    RESOURCE_DIR = os.path.dirname(__file__)
    DATA_DIR = RESOURCE_DIR

app = Flask(
    __name__,
    template_folder=os.path.join(RESOURCE_DIR, "templates"),
    static_folder=os.path.join(RESOURCE_DIR, "static"),
)
app.secret_key = "local-dev-only-not-secret"


def _relative_time(ts_or_iso) -> str:
    try:
        if isinstance(ts_or_iso, (int, float)):
            dt = datetime.fromtimestamp(ts_or_iso, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(ts_or_iso)
    except (ValueError, TypeError):
        return str(ts_or_iso)
    delta = datetime.now(timezone.utc) - dt
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _format_date(ts_or_iso) -> str:
    """Absolute date/time for the left-hand timestamp column, e.g. 'Jul 31 · 2:14 PM'."""
    try:
        if isinstance(ts_or_iso, (int, float)):
            dt = datetime.fromtimestamp(ts_or_iso, tz=timezone.utc).astimezone()
        else:
            dt = datetime.fromisoformat(ts_or_iso).astimezone()
    except (ValueError, TypeError):
        return str(ts_or_iso)
    time_str = dt.strftime("%I:%M %p")
    if time_str.startswith("0"):
        time_str = time_str[1:]
    return f"{dt.strftime('%b')} {dt.day} \u00b7 {time_str}"


app.jinja_env.filters["relative_time"] = _relative_time
app.jinja_env.filters["format_date"] = _format_date


def _recluster_and_cache(config: dict, errors: list = None) -> list:
    """Reclusters the FULL persistent article store (not just whatever
    came back on the latest pull) and writes the result to cache.json,
    so events built up over many refreshes stay on the timeline instead
    of disappearing once a story rolls off a source's live RSS feed."""
    all_articles = load_articles()
    events = cluster_articles(
        all_articles,
        threshold=config.get("cluster_threshold", 0.42),
        window_hours=config.get("cluster_window_hours", 36),
    )
    save_cache({
        "last_run": datetime.now(timezone.utc).isoformat(),
        "events": events,
        "errors": errors or [],
    })
    return events


def _new_event_count(config: dict, cache: dict, dismissed: set) -> int:
    last_viewed = config.get("last_viewed_ts", 0)
    return sum(
        1 for e in cache.get("events", [])
        if e["id"] not in dismissed and e.get("last_seen_ts", 0) > last_viewed
    )


@app.context_processor
def inject_shared_data():
    config = load_config()
    cache = load_cache()
    dismissed = load_dismissed()
    return {"new_count": _new_event_count(config, cache, dismissed)}


@app.route("/")
def index():
    config = load_config()
    cache = load_cache()
    dismissed = load_dismissed()
    active_sources = get_active_sources(config)
    show_hidden = request.args.get("show_hidden") == "1"

    all_events = cache.get("events", [])
    last_viewed = config.get("last_viewed_ts", 0)

    for e in all_events:
        e["is_new"] = e["id"] not in dismissed and e.get("last_seen_ts", 0) > last_viewed
        e["is_hidden"] = e["id"] in dismissed

    visible_events = [e for e in all_events if not e["is_hidden"] or show_hidden]
    hidden_count = sum(1 for e in all_events if e["is_hidden"])

    timelines = load_timelines()

    # Mark everything as read now that the timeline has been opened —
    # after building is_new above, so this pageload still shows the tags.
    config["last_viewed_ts"] = time.time()
    save_config(config)

    return render_template(
        "index.html",
        events=visible_events,
        last_run=cache.get("last_run"),
        errors=cache.get("errors", []),
        active_count=len(active_sources),
        show_hidden=show_hidden,
        hidden_count=hidden_count,
        timelines=timelines,
    )


@app.route("/events/<event_id>/hide", methods=["POST"])
def hide_event(event_id):
    dismissed = load_dismissed()
    dismissed.add(event_id)
    save_dismissed(dismissed)
    return redirect(request.referrer or url_for("index"))


@app.route("/events/<event_id>/unhide", methods=["POST"])
def unhide_event(event_id):
    dismissed = load_dismissed()
    dismissed.discard(event_id)
    save_dismissed(dismissed)
    return redirect(request.referrer or url_for("index"))


@app.route("/refresh", methods=["POST"])
def refresh():
    config = load_config()
    active_sources = get_active_sources(config)

    if not active_sources:
        flash("No sources are turned on yet. Go to Settings and pick at least one.", "error")
        return redirect(url_for("index"))

    fetched, errors = fetch_all(active_sources)

    existing = load_articles()
    merged, added = merge_articles(existing, fetched, retention_days=config.get("retention_days", 45))
    save_articles(merged)

    events = _recluster_and_cache(config, errors)

    if not fetched and not merged:
        flash("No articles came back from any enabled source. See errors below.", "error")
        return redirect(url_for("index"))

    if errors:
        flash(f"Pulled {added} new article(s), but {len(errors)} source(s) had trouble — see details below.", "warning")
    else:
        flash(f"Pulled {added} new article(s) from {len(active_sources)} source(s). Timeline now has {len(events)} events going back {config.get('retention_days', 45)} days.", "success")

    return redirect(url_for("index"))


# ---------- Custom timelines ----------

@app.route("/timelines")
def timelines_list():
    timelines = load_timelines()
    timelines_sorted = sorted(timelines, key=lambda t: t.get("created_at", 0), reverse=True)
    return render_template("timelines.html", timelines=timelines_sorted)


@app.route("/timelines/new", methods=["POST"])
def timelines_new():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Give your timeline a name.", "error")
        return redirect(url_for("timelines_list"))

    timelines = load_timelines()
    if find_timeline_by_name(timelines, name):
        flash(f'A timeline called "{name}" already exists.', "error")
        return redirect(url_for("timelines_list"))

    new_t = create_timeline(timelines, name)
    save_timelines(timelines)
    flash(f'Created timeline "{name}".', "success")
    return redirect(url_for("timeline_detail", timeline_id=new_t["id"]))


@app.route("/timelines/add", methods=["POST"])
def timelines_add_story():
    """Adds a story snapshot (from an event card on the main feed) to an
    existing timeline (picked from the dropdown) or a brand new one
    (typed into the adjacent text field — takes priority if filled in)."""
    story = {
        "headline": request.form.get("headline", "").strip(),
        "link": request.form.get("link", "").strip(),
        "sources": request.form.get("sources", "").strip(),
        "published": request.form.get("published", "").strip(),
        "published_ts": float(request.form.get("published_ts") or 0),
        "added_at": time.time(),
    }
    if not story["headline"]:
        flash("Couldn't add that story — missing headline.", "error")
        return redirect(request.referrer or url_for("index"))

    new_name = request.form.get("new_timeline_name", "").strip()
    existing_id = request.form.get("existing_timeline", "").strip()

    timelines = load_timelines()

    if new_name:
        target = find_timeline_by_name(timelines, new_name)
        if not target:
            target = create_timeline(timelines, new_name)
    elif existing_id:
        target = find_timeline(timelines, existing_id)
    else:
        target = None

    if not target:
        flash("Pick an existing timeline or type a name for a new one.", "error")
        return redirect(request.referrer or url_for("index"))

    added = add_story_to_timeline(target, story)
    save_timelines(timelines)

    if added:
        flash(f'Added to "{target["name"]}".', "success")
    else:
        flash(f'That story is already on "{target["name"]}".', "warning")

    return redirect(request.referrer or url_for("index"))


@app.route("/timelines/<timeline_id>")
def timeline_detail(timeline_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline:
        flash("That timeline doesn't exist (maybe it was deleted).", "error")
        return redirect(url_for("timelines_list"))

    stories = sorted(timeline["stories"], key=lambda s: s.get("published_ts", 0))
    return render_template("timeline_detail.html", timeline=timeline, stories=stories)


@app.route("/timelines/<timeline_id>/remove", methods=["POST"])
def timeline_remove_story(timeline_id):
    link = request.form.get("link", "")
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if timeline:
        timeline["stories"] = [s for s in timeline["stories"] if s.get("link") != link]
        save_timelines(timelines)
        flash("Removed from timeline.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/delete", methods=["POST"])
def timeline_delete(timeline_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if timeline:
        timelines.remove(timeline)
        save_timelines(timelines)
        flash(f'Deleted "{timeline["name"]}".', "success")
    return redirect(url_for("timelines_list"))


# ---------- Settings ----------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    config = load_config()

    if request.method == "POST":
        action = request.form.get("action", "save")

        if action == "add_custom":
            name = request.form.get("custom_name", "").strip()
            url = request.form.get("custom_url", "").strip()
            if not name or not url:
                flash("Give the custom feed both a name and an RSS URL.", "error")
            else:
                config.setdefault("custom_sources", []).append({"name": name, "url": url})
                save_config(config)
                flash(f"Added custom source: {name}", "success")
            return redirect(url_for("settings"))

        if action == "remove_custom":
            idx = int(request.form.get("index", -1))
            customs = config.get("custom_sources", [])
            if 0 <= idx < len(customs):
                removed = customs.pop(idx)
                save_config(config)
                flash(f"Removed: {removed['name']}", "success")
            return redirect(url_for("settings"))

        # action == "save": update enabled starter outlets + clustering + retention
        enabled = request.form.getlist("starter_enabled")
        config["enabled_starter"] = [k for k in enabled if k in STARTER_SOURCES]
        try:
            config["cluster_threshold"] = max(0.05, min(0.95, float(request.form.get("cluster_threshold", 0.42))))
        except ValueError:
            pass
        try:
            config["cluster_window_hours"] = max(1, float(request.form.get("cluster_window_hours", 36)))
        except ValueError:
            pass
        try:
            config["retention_days"] = max(7, float(request.form.get("retention_days", 45)))
        except ValueError:
            pass
        save_config(config)
        # Retention may have changed — reclustering keeps the timeline in
        # sync with the new cutoff without waiting for the next pull.
        _recluster_and_cache(config, load_cache().get("errors", []))
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        config=config,
        starter_sources=STARTER_SOURCES,
    )


def _open_browser():
    webbrowser.open("http://127.0.0.1:8765")


if __name__ == "__main__":
    debug_mode = os.environ.get("NEWS_TIMELINE_DEBUG") == "1"
    if not debug_mode:
        threading.Timer(1.25, _open_browser).start()
    app.run(host="127.0.0.1", port=8765, debug=debug_mode, use_reloader=False)
