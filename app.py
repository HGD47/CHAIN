import os
import sys
import threading
import time
import uuid
import webbrowser
import logging
from datetime import datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, flash, Response

from config_store import (
    load_config, save_config, get_active_sources,
    load_articles, save_articles, merge_articles, get_articles_storage_mb,
    load_dismissed, save_dismissed,
    load_timelines, save_timelines, find_timeline, find_timeline_by_name,
    create_timeline, add_story_to_timeline, find_story,
    load_notifications, save_notifications, add_notification, has_uncleared_of_kind,
)
from sources import STARTER_SOURCES, SOURCE_INFO
from fetcher import fetch_all
from rule_engine import find_matches, MAX_KEYWORDS
from body_fetch import fetch_body_text
from region_tags import REGION_DEFS, tag_regions

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

# The console window otherwise prints a line for every single request
# (every page load, every asset, every background auto-pull check) —
# quiet that down to just startup/errors.
logging.getLogger("werkzeug").setLevel(logging.ERROR)

MAX_TIMELINE_ROWS = 300  # simple cap so a months-old install still loads fast
MAX_BODY_FETCHES_PER_CHECK = 25  # keep a single rule-check from hanging on slow/blocked sites


def _ensure_bodies_fetched(candidate_articles: list) -> None:
    """For rules with search_body on, fetches full article text for any
    candidate that doesn't have it cached yet, capped per check so one
    rule with hundreds of candidates can't hang the request for minutes.
    Mutates articles.json in place; candidate_articles dicts (same
    objects as in the freshly-loaded list) are updated too."""
    to_fetch = [a for a in candidate_articles if not a.get("body_text") and a.get("link")][:MAX_BODY_FETCHES_PER_CHECK]
    if not to_fetch:
        return
    for a in to_fetch:
        a["body_text"] = fetch_body_text(a["link"]) or " "  # store a space, not "", to mark "tried"
        a["body_fetched_ts"] = time.time()

    all_articles = load_articles()
    by_id = {a["id"]: a for a in all_articles}
    for a in to_fetch:
        if a["id"] in by_id:
            by_id[a["id"]]["body_text"] = a["body_text"]
            by_id[a["id"]]["body_fetched_ts"] = a["body_fetched_ts"]
    save_articles(all_articles)


def _apply_timeline_rule(timeline: dict, all_articles: list) -> int:
    rule = timeline.get("rule")
    if not rule:
        return 0

    candidates = all_articles
    if rule.get("search_body"):
        # Narrow to articles whose title/summary already hit at least one
        # keyword before spending a network fetch on the rest, to keep
        # the fetch count down.
        from rule_engine import _searchable_text, _clean_keywords
        keywords = [k.lower() for k in _clean_keywords(rule.get("keywords"))]
        prelim = [a for a in all_articles if any(k in _searchable_text(a, False) for k in keywords)]
        _ensure_bodies_fetched(prelim)
        # Reload so the freshly-cached body_text is reflected.
        all_articles[:] = load_articles()
        candidates = all_articles

    matches = find_matches(rule, candidates)
    added = 0
    for article in matches:
        if add_story_to_timeline(timeline, _story_from_article(article)):
            added += 1
    return added


def _apply_all_rules() -> None:
    timelines = load_timelines()
    all_articles = load_articles()
    changed = False
    for t in timelines:
        if t.get("rule"):
            if _apply_timeline_rule(t, all_articles) > 0:
                changed = True
    if changed:
        save_timelines(timelines)


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


def _to_datetime_local_value(ts) -> str:
    """Formats a unix timestamp for use as a <input type="datetime-local">
    value/default, in the browser's (i.e. this machine's) local time."""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc).astimezone()
    except (ValueError, TypeError):
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M")


app.jinja_env.filters["relative_time"] = _relative_time
app.jinja_env.filters["format_date"] = _format_date
app.jinja_env.filters["datetime_local"] = _to_datetime_local_value


# ---------- Shared pull logic (used by manual Refresh AND background auto-pull) ----------

def _check_storage_and_notify(config: dict) -> None:
    limit = config.get("storage_limit_mb", 0)
    if not limit:
        return
    used = get_articles_storage_mb()
    if used < limit:
        return
    notifications = load_notifications()
    if has_uncleared_of_kind(notifications, "storage_warning"):
        return  # don't spam — one open warning at a time
    add_notification(
        notifications, "storage_warning",
        f"Your saved news history is using {used} MB, over your {limit} MB limit.",
        [{"source": "Storage", "error": "Nothing was deleted — lower your retention days in Settings, or raise/turn off the limit."}],
    )
    save_notifications(notifications)


def _do_pull(config: dict) -> tuple:
    """Fetches every enabled source, merges into the persistent article
    store, and updates bookkeeping. Returns (added_count, errors)."""
    active_sources = get_active_sources(config)
    if not active_sources:
        return None, []

    fetched, errors = fetch_all(active_sources)

    existing = load_articles()
    merged, added = merge_articles(existing, fetched, retention_days=config.get("retention_days", 45))
    save_articles(merged)

    config["last_pull_ts"] = time.time()
    config["last_pull_errors"] = errors
    save_config(config)

    if errors:
        notifications = load_notifications()
        add_notification(
            notifications, "source_error",
            f"{len(errors)} source{'s' if len(errors) != 1 else ''} had trouble on the last pull",
            errors,
        )
        save_notifications(notifications)

    _check_storage_and_notify(config)
    _apply_all_rules()
    return added, errors


def _background_auto_pull_loop():
    """Runs for the lifetime of the process. Only ever pulls if
    auto_pull_enabled is on — off by default. This can only fill gaps
    while the app itself is left running; it can't retrieve news from
    while your computer was off or the app was closed."""
    while True:
        time.sleep(60)
        try:
            config = load_config()
            if not config.get("auto_pull_enabled"):
                continue
            interval_s = max(1, config.get("auto_pull_interval_hours", 4)) * 3600
            last = config.get("last_pull_ts") or 0
            if time.time() - last >= interval_s:
                _do_pull(config)
        except Exception:
            # Never let a background hiccup take the whole app down.
            continue


# ---------- Context available to every template ----------

@app.context_processor
def inject_shared_data():
    config = load_config()
    dismissed = load_dismissed()
    articles = load_articles()
    last_viewed = config.get("last_viewed_ts", 0)
    new_count = sum(
        1 for a in articles
        if a["id"] not in dismissed and a.get("first_stored_ts", 0) > last_viewed
    )
    notif_count = sum(1 for n in load_notifications() if not n["cleared"])
    return {
        "new_count": new_count,
        "notif_count": notif_count,
        "theme": config.get("theme", "dark"),
        "is_windows": os.name == "nt",
        "console_visible": _console_visible,
    }


# ---------- Timeline ----------

@app.route("/")
def index():
    config = load_config()
    dismissed = load_dismissed()
    active_sources = get_active_sources(config)
    show_hidden = request.args.get("show_hidden") == "1"
    query = request.args.get("q", "").strip()
    source_filter = request.args.get("source_filter", "").strip()
    region_filter = request.args.get("region_filter", "").strip()
    sort_by = request.args.get("sort", "newest")
    select_mode = request.args.get("select") == "1"

    articles = load_articles()
    last_viewed = config.get("last_viewed_ts", 0)

    for a in articles:
        a["is_new"] = a["id"] not in dismissed and a.get("first_stored_ts", 0) > last_viewed
        a["is_hidden"] = a["id"] in dismissed

    visible = [a for a in articles if not a["is_hidden"] or show_hidden]

    if query:
        q_lower = query.lower()
        visible = [a for a in visible if q_lower in a["title"].lower() or q_lower in a.get("summary", "").lower()]

    if source_filter:
        visible = [a for a in visible if a["source_name"] == source_filter]

    if region_filter:
        visible = [a for a in visible if region_filter in tag_regions(a)]

    sort_map = {
        "newest": (lambda a: a["published_ts"], True),
        "oldest": (lambda a: a["published_ts"], False),
        "headline_az": (lambda a: a["title"].lower(), False),
        "headline_za": (lambda a: a["title"].lower(), True),
        "source_az": (lambda a: a["source_name"].lower(), False),
        "source_za": (lambda a: a["source_name"].lower(), True),
    }
    key_fn, reverse = sort_map.get(sort_by, sort_map["newest"])
    visible = sorted(visible, key=key_fn, reverse=reverse)

    truncated = len(visible) > MAX_TIMELINE_ROWS
    visible = visible[:MAX_TIMELINE_ROWS]

    # Region tags only computed for what's actually being shown — cheap
    # regex work, but no point running it over the full history every load.
    for a in visible:
        a["region_tags"] = [(k, REGION_DEFS[k].get("display", REGION_DEFS[k]["label"])) for k in tag_regions(a)]

    hidden_count = sum(1 for a in articles if a["is_hidden"])
    all_source_names = sorted({a["source_name"] for a in articles})
    timelines = load_timelines()

    config["last_viewed_ts"] = time.time()
    save_config(config)

    return render_template(
        "index.html",
        articles=visible,
        truncated=truncated,
        last_pull_ts=config.get("last_pull_ts"),
        pull_errors=config.get("last_pull_errors", []),
        active_count=len(active_sources),
        show_hidden=show_hidden,
        select_mode=select_mode,
        timelines=timelines,
        query=query,
        source_filter=source_filter,
        region_filter=region_filter,
        sort_by=sort_by,
        all_source_names=all_source_names,
        hidden_count=hidden_count,
        region_defs=REGION_DEFS,
    )


@app.route("/articles/<article_id>/hide", methods=["POST"])
def hide_article(article_id):
    dismissed = load_dismissed()
    dismissed.add(article_id)
    save_dismissed(dismissed)
    return redirect(request.referrer or url_for("index"))


@app.route("/articles/<article_id>/unhide", methods=["POST"])
def unhide_article(article_id):
    dismissed = load_dismissed()
    dismissed.discard(article_id)
    save_dismissed(dismissed)
    return redirect(request.referrer or url_for("index"))


@app.route("/refresh", methods=["POST"])
def refresh():
    config = load_config()
    added, errors = _do_pull(config)

    if added is None:
        flash("No sources are turned on yet. Go to Sources and pick at least one.", "error")
    elif errors:
        flash(f"Pulled {added} new article(s), but {len(errors)} source(s) had trouble — see Notifications.", "warning")
    else:
        flash(f"Pulled {added} new article(s).", "success")

    return redirect(url_for("index"))


# ---------- Notifications ----------

@app.route("/notifications")
def notifications_page():
    notifications = load_notifications()
    notifications_sorted = sorted(notifications, key=lambda n: n["created_at"], reverse=True)
    return render_template("notifications.html", notifications=notifications_sorted)


@app.route("/notifications/<notif_id>/clear", methods=["POST"])
def notification_clear(notif_id):
    notifications = load_notifications()
    for n in notifications:
        if n["id"] == notif_id:
            n["cleared"] = True
    save_notifications(notifications)
    return redirect(url_for("notifications_page"))


@app.route("/notifications/clear_all", methods=["POST"])
def notifications_clear_all():
    notifications = load_notifications()
    for n in notifications:
        n["cleared"] = True
    save_notifications(notifications)
    return redirect(url_for("notifications_page"))


# ---------- Custom timelines ("Your Timelines") ----------

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


def _story_from_article(article: dict) -> dict:
    return {
        "headline": article["title"],
        "link": article["link"],
        "sources": article["source_name"],
        "published": article["published"],
        "published_ts": article["published_ts"],
        "added_at": time.time(),
    }


@app.route("/timelines/add", methods=["POST"])
def timelines_add_story():
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

    target, error = _resolve_timeline_target(request.form)
    if error:
        flash(error, "error")
        return redirect(request.referrer or url_for("index"))

    timelines = load_timelines()
    target = find_timeline(timelines, target["id"])
    added = add_story_to_timeline(target, story)
    save_timelines(timelines)
    flash(f'Added to "{target["name"]}".' if added else f'Already on "{target["name"]}".', "success" if added else "warning")
    return redirect(request.referrer or url_for("index"))


@app.route("/timelines/add_bulk", methods=["POST"])
def timelines_add_bulk():
    """Adds every checked story (Select mode on the Timeline page) to one
    target timeline in a single action."""
    article_ids = request.form.getlist("article_ids")
    if not article_ids:
        flash("Select at least one story first.", "error")
        return redirect(request.referrer or url_for("index"))

    timelines = load_timelines()
    new_name = request.form.get("new_timeline_name", "").strip()
    existing_id = request.form.get("existing_timeline", "").strip()

    if new_name:
        target = find_timeline_by_name(timelines, new_name) or create_timeline(timelines, new_name)
    elif existing_id:
        target = find_timeline(timelines, existing_id)
    else:
        target = None

    if not target:
        flash("Pick an existing timeline or type a name for a new one.", "error")
        return redirect(request.referrer or url_for("index"))

    articles_by_id = {a["id"]: a for a in load_articles()}
    added_count = 0
    for aid in article_ids:
        article = articles_by_id.get(aid)
        if not article:
            continue
        if add_story_to_timeline(target, _story_from_article(article)):
            added_count += 1

    save_timelines(timelines)
    flash(f'Added {added_count} stor{"y" if added_count == 1 else "ies"} to "{target["name"]}".', "success")
    return redirect(request.referrer or url_for("index"))


def _resolve_timeline_target(form):
    new_name = form.get("new_timeline_name", "").strip()
    existing_id = form.get("existing_timeline", "").strip()
    timelines = load_timelines()
    if new_name:
        t = find_timeline_by_name(timelines, new_name)
        if not t:
            t = create_timeline(timelines, new_name)
            save_timelines(timelines)
        return t, None
    if existing_id:
        t = find_timeline(timelines, existing_id)
        if t:
            return t, None
    return None, "Pick an existing timeline or type a name for a new one."


@app.route("/timelines/<timeline_id>/rule", methods=["POST"])
def timeline_save_rule(timeline_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline:
        flash("That timeline doesn't exist.", "error")
        return redirect(url_for("timelines_list"))

    keywords = [request.form.get(f"keyword{i}", "").strip() for i in range(1, MAX_KEYWORDS + 1)]
    keywords = [k for k in keywords if k]
    if not keywords:
        flash("Enter at least one keyword.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))

    mode = request.form.get("mode", "same_article")
    try:
        window_days = max(1, int(request.form.get("window_days", 21)))
    except ValueError:
        window_days = 21

    timeline["rule"] = {
        "keywords": keywords,
        "mode": mode,
        "window_days": window_days,
        "search_body": request.form.get("search_body") == "on",
    }
    save_timelines(timelines)

    added = _apply_timeline_rule(timeline, load_articles())
    save_timelines(timelines)

    flash(f"Rule saved. {added} matching stor{'y' if added == 1 else 'ies'} added.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/rule/check", methods=["POST"])
def timeline_check_rule(timeline_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline or not timeline.get("rule"):
        flash("No rule set on this timeline.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))

    added = _apply_timeline_rule(timeline, load_articles())
    save_timelines(timelines)
    flash(f"Checked. {added} new matching stor{'y' if added == 1 else 'ies'} added.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/rule/clear", methods=["POST"])
def timeline_clear_rule(timeline_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if timeline and "rule" in timeline:
        del timeline["rule"]
        save_timelines(timelines)
        flash("Rule removed. Stories already added stay on the timeline.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>")
def timeline_detail(timeline_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline:
        flash("That timeline doesn't exist (maybe it was deleted).", "error")
        return redirect(url_for("timelines_list"))

    def effective_ts(s):
        return s.get("display_ts") if s.get("display_ts") else s.get("published_ts", 0)

    stories = sorted(timeline["stories"], key=effective_ts)
    for s in stories:
        s = s  # (already a dict reference from timeline["stories"])
        s["effective_ts"] = effective_ts(s)
        s["is_moved"] = bool(s.get("display_ts")) and abs(s["display_ts"] - s.get("published_ts", 0)) > 60
        s["region_tags"] = [
            (k, REGION_DEFS[k].get("display", REGION_DEFS[k]["label"]))
            for k in tag_regions({"title": s.get("headline", ""), "summary": ""})
        ]

    return render_template("timeline_detail.html", timeline=timeline, stories=stories)


@app.route("/timelines/<timeline_id>/remove", methods=["POST"])
def timeline_remove_story(timeline_id):
    story_id = request.form.get("story_id", "")
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if timeline:
        timeline["stories"] = [s for s in timeline["stories"] if s.get("id") != story_id]
        save_timelines(timelines)
        flash("Removed from timeline.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/add_event", methods=["POST"])
def timeline_add_custom_event(timeline_id):
    """Adds a manually-created event to a timeline — not pulled from any
    article. Useful for marking when something actually happened, even
    if no single article covers just that moment."""
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline:
        flash("That timeline doesn't exist.", "error")
        return redirect(url_for("timelines_list"))

    title = request.form.get("title", "").strip()
    raw_dt = request.form.get("event_datetime", "").strip()
    link = request.form.get("link", "").strip()
    note = request.form.get("note", "").strip()

    if not title or not raw_dt:
        flash("A custom event needs at least a title and a date.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))

    try:
        # datetime-local inputs have no timezone info — treat as the
        # browser's local time, same as everywhere else dates are shown.
        dt_local = datetime.fromisoformat(raw_dt).astimezone()
    except ValueError:
        flash("Couldn't read that date/time.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))

    story = {
        "id": uuid.uuid4().hex[:12],
        "headline": title,
        "link": link,
        "sources": "Custom event",
        "published": dt_local.astimezone(timezone.utc).isoformat(),
        "published_ts": dt_local.timestamp(),
        "display_ts": None,
        "is_custom": True,
        "note": note,
        "added_at": time.time(),
    }
    timeline["stories"].append(story)
    save_timelines(timelines)
    flash(f'Added custom event "{title}".', "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/story/<story_id>/set_date", methods=["POST"])
def timeline_set_story_date(timeline_id, story_id):
    """Overrides where a story sits on the timeline — e.g. moving a
    delayed report to sit alongside other coverage of when the event it
    describes actually happened, rather than when it was published. The
    story's real published date is kept and shown alongside it whenever
    it's been moved, so the discrepancy stays visible instead of hidden."""
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline:
        flash("That timeline doesn't exist.", "error")
        return redirect(url_for("timelines_list"))

    story = find_story(timeline, story_id)
    if not story:
        flash("That story isn't on this timeline.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))

    raw_dt = request.form.get("display_datetime", "").strip()
    if not raw_dt:
        flash("Couldn't read that date/time.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))
    try:
        dt_local = datetime.fromisoformat(raw_dt).astimezone()
    except ValueError:
        flash("Couldn't read that date/time.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))

    story["display_ts"] = dt_local.timestamp()
    save_timelines(timelines)
    flash("Moved on the timeline.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/story/<story_id>/reset_date", methods=["POST"])
def timeline_reset_story_date(timeline_id, story_id):
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if timeline:
        story = find_story(timeline, story_id)
        if story:
            story["display_ts"] = None
            save_timelines(timelines)
            flash("Reset to its original date.", "success")
    return redirect(url_for("timeline_detail", timeline_id=timeline_id))


@app.route("/timelines/<timeline_id>/rename", methods=["POST"])
def timeline_rename(timeline_id):
    new_name = request.form.get("name", "").strip()
    timelines = load_timelines()
    timeline = find_timeline(timelines, timeline_id)
    if not timeline:
        flash("That timeline doesn't exist.", "error")
        return redirect(url_for("timelines_list"))
    if not new_name:
        flash("Timeline name can't be empty.", "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))
    other = find_timeline_by_name(timelines, new_name)
    if other and other["id"] != timeline_id:
        flash(f'A timeline called "{new_name}" already exists.', "error")
        return redirect(url_for("timeline_detail", timeline_id=timeline_id))
    timeline["name"] = new_name
    save_timelines(timelines)
    flash("Renamed.", "success")
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


# ---------- Regions ----------

@app.route("/regions")
def regions_list():
    query = request.args.get("q", "").strip().lower()
    items = sorted(REGION_DEFS.items(), key=lambda kv: kv[1]["label"])
    if query:
        items = [(k, v) for k, v in items if query in v["label"].lower()]
    return render_template("regions.html", regions=items, query=request.args.get("q", ""))


@app.route("/regions/<region_key>")
def region_detail(region_key):
    info = REGION_DEFS.get(region_key)
    if not info:
        flash("That region doesn't exist.", "error")
        return redirect(url_for("regions_list"))

    articles = load_articles()
    dismissed = load_dismissed()
    matches = []
    for a in articles:
        if a["id"] in dismissed:
            continue
        tags = tag_regions(a)
        if region_key in tags:
            a = dict(a)
            a["region_tags"] = [(k, REGION_DEFS[k].get("display", REGION_DEFS[k]["label"])) for k in tags]
            matches.append(a)
    matches.sort(key=lambda a: a["published_ts"], reverse=True)
    matches = matches[:MAX_TIMELINE_ROWS]

    return render_template("region_detail.html", key=region_key, info=info, articles=matches)


# ---------- Sources (pick outlets + read about them) ----------

@app.route("/sources", methods=["GET", "POST"])
def sources_page():
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
            return redirect(url_for("sources_page"))

        if action == "remove_custom":
            idx = int(request.form.get("index", -1))
            customs = config.get("custom_sources", [])
            if 0 <= idx < len(customs):
                removed = customs.pop(idx)
                save_config(config)
                flash(f"Removed: {removed['name']}", "success")
            return redirect(url_for("sources_page"))

        enabled = request.form.getlist("starter_enabled")
        config["enabled_starter"] = [k for k in enabled if k in STARTER_SOURCES]
        save_config(config)
        flash("Sources updated.", "success")
        return redirect(url_for("sources_page"))

    return render_template("sources.html", config=config, starter_sources=STARTER_SOURCES, source_info=SOURCE_INFO)


# ---------- Settings (tuning, not source selection) ----------

@app.route("/settings", methods=["GET", "POST"])
def settings():
    config = load_config()

    if request.method == "POST":
        try:
            config["retention_days"] = max(7, float(request.form.get("retention_days", 45)))
        except ValueError:
            pass
        config["auto_pull_enabled"] = request.form.get("auto_pull_enabled") == "on"
        try:
            config["auto_pull_interval_hours"] = max(1, float(request.form.get("auto_pull_interval_hours", 4)))
        except ValueError:
            pass
        try:
            config["storage_limit_mb"] = max(0, float(request.form.get("storage_limit_mb", 0)))
        except ValueError:
            pass
        save_config(config)
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        config=config,
        storage_used_mb=get_articles_storage_mb(),
    )


def _open_browser():
    webbrowser.open("http://127.0.0.1:8765")


@app.route("/theme/toggle", methods=["POST"])
def theme_toggle():
    config = load_config()
    config["theme"] = "light" if config.get("theme", "dark") == "dark" else "dark"
    save_config(config)
    return redirect(request.referrer or url_for("index"))


# ---------- Console window visibility (Windows only) ----------
# There's no cross-platform way to hide/show a terminal window without
# extra dependencies, so this is Windows-only (via ctypes, no pip install
# needed) and the button simply doesn't render on Mac/Linux — see base.html.
_console_visible = True


@app.route("/console/toggle", methods=["POST"])
def console_toggle():
    global _console_visible
    if os.name == "nt":
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            SW_HIDE, SW_SHOW = 0, 5
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE if _console_visible else SW_SHOW)
            _console_visible = not _console_visible
    return redirect(request.referrer or url_for("index"))


# ---------- Auto-close the browser tab if the server process dies ----------
# The page keeps one of these connections open via EventSource. If the
# Python process ends for ANY reason — the Stop button, the console
# window being closed, the terminal being killed — this connection
# breaks, the page's onerror handler fires, and it attempts to close
# itself. (Browsers only allow script-driven tabs to actually close
# themselves for tabs opened by a script in the first place, which is
# how Wire opens its tab — but some browsers block this regardless as a
# hard security rule with no exception, so it's a best-effort, not a
# guarantee.)
@app.route("/events")
def sse_events():
    def stream():
        try:
            while True:
                yield ": heartbeat\n\n"
                time.sleep(2)
        except GeneratorExit:
            return
    return Response(stream(), mimetype="text/event-stream")


@app.route("/stop", methods=["POST"])
def stop():
    def _shutdown():
        time.sleep(0.4)
        os._exit(0)
    threading.Thread(target=_shutdown, daemon=True).start()
    return render_template("stopped.html")


if __name__ == "__main__":
    debug_mode = os.environ.get("NEWS_TIMELINE_DEBUG") == "1"
    if not debug_mode:
        threading.Timer(1.25, _open_browser).start()
    threading.Thread(target=_background_auto_pull_loop, daemon=True).start()
    app.run(host="127.0.0.1", port=8765, debug=debug_mode, use_reloader=False, threaded=True)
