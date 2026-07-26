"""
Speculae Web UI — a beautiful localhost frontend.

Launch:
    python -m speculae.web.server
    speculae-web              (after pip install -e ".[web]")

Binds exclusively to 127.0.0.1:7730.
Your journal never leaves your machine.
"""
from __future__ import annotations

import sys
import webbrowser
from datetime import date, timedelta
from pathlib import Path

try:
    from flask import Flask, Response, g, jsonify, request, send_file, send_from_directory
except ImportError:
    print("\n  Flask is required for the Speculae web UI.")
    print("  Install it with:  pip install flask\n")
    sys.exit(1)

try:
    from speculae import config as cfg_module
    from speculae import db as db_module
    from speculae import insights as insights_module
    from speculae import patterns as patterns_module
    from speculae import wellness as wellness_module
    from speculae.models import Entry
except ImportError as e:
    print(f"\n  Could not import speculae: {e}")
    print("  Install with:  pip install -e .\n")
    sys.exit(1)


VERSION = "0.1.0"
HOST = "127.0.0.1"
PORT = 7730

MAX_IMAGE_BYTES = 8 * 1024 * 1024   # 8 MB — keeps display-quality photos while preventing bloat
def _resolve_static() -> Path:
    """Resolve the static files directory in all execution contexts."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # PyInstaller bundle: try the expected _MEIPASS sub-path first,
        # then fall back to the directory containing the frozen exe.
        candidate = Path(sys._MEIPASS) / "speculae" / "web"
        if (candidate / "index.html").exists():
            return candidate
        # Fallback: PyInstaller may flatten the tree depending on spec flags
        candidate2 = Path(sys._MEIPASS)
        if (candidate2 / "index.html").exists():
            return candidate2
        # Last resort: exe's own directory (one-file extraction temp dir)
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

STATIC = _resolve_static()


app = Flask(__name__)
cfg = cfg_module.load()


def _db() -> db_module.Database:
    if "db" not in g:
        database = db_module.Database(cfg.db_file)
        database.connect()
        g.db = database
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _valid_mood_energy(v):
    try:
        return int(v) if v is not None and 1 <= int(v) <= 5 else None
    except (TypeError, ValueError):
        return None


def _entry_dict(e: Entry) -> dict:
    return {
        "id": e.id,
        "date": e.date.isoformat(),
        "content": e.content,
        "mood": e.mood,
        "energy": e.energy,
        "tags": e.tags,
        "starred": e.starred,
        "agent_id": e.agent_id,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _pattern_dict(p) -> dict:
    return {
        "id": p.id,
        "type": p.type,
        "title": p.title,
        "description": p.description,
        "severity": p.severity,
        "emoji": p.emoji(),
        "entry_date_from": p.entry_date_from.isoformat() if p.entry_date_from else None,
        "entry_date_to": p.entry_date_to.isoformat() if p.entry_date_to else None,
        "data": p.data,
        "agent_id": p.agent_id,
    }


def _image_dict(img) -> dict:
    return {
        "id": img.id,
        "entry_id": img.entry_id,
        "filename": img.filename,
        "mime_type": img.mime_type,
        "file_size": img.file_size,
        "created_at": img.created_at.isoformat() if img.created_at else None,
    }


def _parse_tags(body: dict) -> list[str] | None:
    """Validate and normalise the 'tags' field from a request body.

    Returns a cleaned list of non-empty strings on success.
    Returns None if the value is present but is not a list — callers should
    respond with 400.
    """
    raw = body.get("tags")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return None
    return [t.strip() for t in raw if isinstance(t, str) and t.strip()]


# ── Static ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC, "index.html")


# ── Entries ──────────────────────────────────────────────────────────────────

@app.route("/api/entries", methods=["GET"])
def list_entries():
    try:
        days = int(request.args.get("days", 90))
        if not (1 <= days <= 3650):
            return jsonify({"error": "days must be between 1 and 3650"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "days must be an integer"}), 400

    q             = request.args.get("q", "").strip()
    tag           = request.args.get("tag", "").strip()
    mood          = request.args.get("mood", "").strip()
    starred       = request.args.get("starred", "").strip().lower()
    agent         = request.args.get("agent", "").strip()
    starred_agent = request.args.get("starred_agent", "").strip()

    since     = date.today() - timedelta(days=days)
    agent_id  = agent if agent else None

    with _db() as database:
        if q:
            entries = db_module.search_entries(database, q, limit=100)
        elif tag:
            entries = db_module.list_entries_by_tag(
                database, tag, limit=400, since=since, agent_id=agent_id,
            )
        elif starred_agent:
            entries = db_module.list_entries(
                database,
                limit=400,
                since=since,
                starred_only=True,
                agent_id=starred_agent,
            )
        else:
            starred_only = starred == "true"
            entries = db_module.list_entries(
                database, limit=400, since=since,
                starred_only=starred_only, agent_id=agent_id,
            )

        if mood:
            try:
                mood_val = int(mood)
                entries = [e for e in entries if e.mood == mood_val]
            except ValueError:
                pass

    return jsonify([_entry_dict(e) for e in entries])


@app.route("/api/entries/<date_str>", methods=["GET"])
def get_entries(date_str: str):
    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Use YYYY-MM-DD"}), 400

    with _db() as database:
        entries = db_module.get_entries_for_date(database, entry_date)

    return jsonify([_entry_dict(e) for e in entries])


@app.route("/api/entries/<date_str>", methods=["POST"])
def create_entry(date_str: str):
    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({"error": "Use YYYY-MM-DD"}), 400

    body = request.get_json(silent=True) or {}

    tags = _parse_tags(body)
    if tags is None:
        return jsonify({"error": "'tags' must be a list of strings"}), 400

    entry_id = body.get("id")
    if entry_id:
        with _db() as database:
            existing = db_module.get_entry_by_id(database, entry_id)
            if existing:
                existing.content = body.get("content", "")
                existing.mood = _valid_mood_energy(body.get("mood"))
                existing.energy = _valid_mood_energy(body.get("energy"))
                existing.tags = tags
                existing.starred = bool(body.get("starred", existing.starred))
                saved = db_module.save_entry(database, existing)
                return jsonify(_entry_dict(saved))

    entry = Entry(
        date=entry_date,
        content=body.get("content", ""),
        mood=_valid_mood_energy(body.get("mood")),
        energy=_valid_mood_energy(body.get("energy")),
        tags=tags,
        starred=bool(body.get("starred", False)),
        agent_id=body.get("agent_id"),
    )

    with _db() as database:
        saved = db_module.save_entry(database, entry)

    return jsonify(_entry_dict(saved))


@app.route("/api/entries/by-id/<entry_id>", methods=["GET"])
def get_entry_by_id(entry_id: str):
    with _db() as database:
        entry = db_module.get_entry_by_id(database, entry_id)
    if not entry:
        return jsonify({"error": "not found"}), 404
    return jsonify(_entry_dict(entry))


@app.route("/api/entries/<entry_id>", methods=["PUT"])
def update_entry(entry_id: str):
    with _db() as database:
        entry = db_module.get_entry_by_id(database, entry_id)
        if not entry:
            return jsonify({"error": "not found"}), 404

        body = request.get_json(silent=True) or {}

        if "content" in body:
            entry.content = body["content"]
        if "mood" in body:
            entry.mood = _valid_mood_energy(body["mood"])
        if "energy" in body:
            entry.energy = _valid_mood_energy(body["energy"])
        if "tags" in body:
            entry.tags = [t.strip() for t in body["tags"] if t.strip()]
        if "starred" in body:
            entry.starred = bool(body["starred"])

        saved = db_module.save_entry(database, entry)

    return jsonify(_entry_dict(saved))


@app.route("/api/entries/<entry_id>", methods=["DELETE"])
def delete_entry(entry_id: str):
    with _db() as database:
        db_module.delete_images_for_entry(database, entry_id)
        ok = db_module.delete_entry(database, entry_id)

    return jsonify({"deleted": ok})


@app.route("/api/entries/batch", methods=["DELETE"])
def delete_entries_batch():
    data = request.get_json(silent=True) or {}
    entry_ids = data.get("ids", [])
    if not isinstance(entry_ids, list) or not entry_ids:
        return jsonify({"error": "ids array required"}), 400

    with _db() as database:
        count = db_module.delete_entries_batch(database, entry_ids)

    return jsonify({"deleted_count": count})


# ── Images ───────────────────────────────────────────────────────────────────

@app.route("/api/entries/<entry_id>/images", methods=["GET"])
def list_images(entry_id: str):
    with _db() as database:
        images = db_module.get_images_for_entry(database, entry_id)
    return jsonify([_image_dict(img) for img in images])


@app.route("/api/entries/<entry_id>/images", methods=["POST"])
def upload_image(entry_id: str):
    with _db() as database:
        entry = db_module.get_entry_by_id(database, entry_id)
        if not entry:
            return jsonify({"error": "entry not found"}), 404

    if "file" in request.files:
        f = request.files["file"]
        data = f.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            return jsonify({
                "error": f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit."
            }), 413
        filename = f.filename or "image.png"
        mime_type = f.content_type or "image/png"
    else:
        body = request.get_json(silent=True) or {}
        data_b64 = body.get("data", "")
        filename = body.get("filename", "image.png")
        mime_type = body.get("mime_type", "image/png")
        import base64
        try:
            data = base64.b64decode(data_b64)
        except Exception:
            return jsonify({"error": "invalid base64 data"}), 400
        if len(data) > MAX_IMAGE_BYTES:
            return jsonify({
                "error": f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB limit."
            }), 413

    if not data:
        return jsonify({"error": "no image data"}), 400

    with _db() as database:
        img = db_module.save_image(database, entry_id, filename, data, mime_type)

    return jsonify(_image_dict(img))


@app.route("/api/images/<image_id>", methods=["GET"])
def serve_image(image_id: str):
    with _db() as database:
        img = db_module.get_image_by_id(database, image_id, load_data=False)
        if not img:
            return jsonify({"error": "not found"}), 404
        path = db_module.get_image_file_path(database, image_id)
    if path:
        return send_file(
            path,
            mimetype=img.mime_type,
            download_name=img.filename,
            conditional=True,
        )
    # Legacy fallback: load bytes if path missing but row exists
    with _db() as database:
        img = db_module.get_image_by_id(database, image_id, load_data=True)
    if not img or not img.data:
        return jsonify({"error": "not found"}), 404
    return Response(
        img.data,
        mimetype=img.mime_type,
        headers={"Content-Disposition": f'inline; filename="{img.filename}"'},
    )


@app.route("/api/images/<image_id>", methods=["DELETE"])
def delete_image(image_id: str):
    with _db() as database:
        ok = db_module.delete_image(database, image_id)
    return jsonify({"deleted": ok})


# ── Calendar ─────────────────────────────────────────────────────────────────

@app.route("/api/calendar", methods=["GET"])
def calendar():
    months = int(request.args.get("months", 4))
    since = date.today() - timedelta(days=months * 31 + 7)

    with _db() as database:
        entries = db_module.list_entries(database, limit=600, since=since)

    result = {}
    for e in entries:
        ds = e.date.isoformat()
        if ds not in result:
            result[ds] = {
                "moods": [], "energies": [], "has_content": False,
                "tags": set(), "words": 0, "count": 0,
            }
        acc = result[ds]
        if e.mood is not None:
            acc["moods"].append(e.mood)
        if e.energy is not None:
            acc["energies"].append(e.energy)
        if e.content.strip():
            acc["has_content"] = True
        acc["tags"].update(e.tags)
        acc["words"] += len(e.content.split()) if e.content else 0
        acc["count"] += 1

    def avg(vals):
        return round(sum(vals) / len(vals)) if vals else None

    return jsonify({
        ds: {
            "mood": avg(d["moods"]), "energy": avg(d["energies"]),
            "has_content": d["has_content"], "tags": list(d["tags"]),
            "words": d["words"], "count": d["count"],
        }
        for ds, d in result.items()
    })


# ── Patterns ─────────────────────────────────────────────────────────────────

@app.route("/api/patterns", methods=["GET"])
def get_patterns():
    refresh = request.args.get("refresh", "false").lower() == "true"
    agent = request.args.get("agent", "").strip() or None

    with _db() as database:
        cached = db_module.list_patterns(database, agent_id=agent)
        count = db_module.entry_count(database)

        if (refresh or not cached) and count >= cfg.patterns.min_entries_for_patterns:
            entries = db_module.list_entries(database, limit=1000, agent_id=agent)
            detected = patterns_module.run_all(entries, cfg.patterns)
            db_module.save_patterns(database, detected, agent_id=agent)
            cached = detected

    return jsonify([_pattern_dict(p) for p in cached])


# ── Insights ─────────────────────────────────────────────────────────────────

@app.route("/api/insights", methods=["GET"])
def get_insights():
    refresh = request.args.get("refresh", "false").lower() == "true"
    days = int(request.args.get("days", 7))
    agent = request.args.get("agent", "").strip() or None

    with _db() as database:
        cached = db_module.latest_insight(database)

        if refresh or not cached:
            if agent:
                entries = db_module.list_entries(database, limit=1000, agent_id=agent)
                pats = db_module.list_patterns(database, agent_id=agent)
            else:
                entries = db_module.list_entries(database, limit=1000, human_only=True)
                pats = db_module.list_patterns(database)
            end = date.today()
            start = end - timedelta(days=days - 1)
            insight = insights_module.generate(entries, pats, start, end, cfg.ai)
            db_module.save_insight(database, insight)
            cached = insight

    if not cached:
        return jsonify(None)

    return jsonify({
        "id": cached.id,
        "period_start": cached.period_start.isoformat(),
        "period_end": cached.period_end.isoformat(),
        "content": cached.content,
        "type": cached.type,
        "generated_at": cached.generated_at.isoformat(),
    })


# ── Stats ────────────────────────────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    agent = request.args.get("agent", "").strip()

    with _db() as database:
        if agent:
            entries = db_module.list_entries(database, limit=10000, agent_id=agent)
            count = len(entries)
            first = min((e.date for e in entries), default=None)
            last = max((e.date for e in entries), default=None)
        else:
            count = db_module.entry_count(database)
            first, last = db_module.date_range(database)
            entries = db_module.list_entries(
                database, limit=200, since=date.today() - timedelta(days=30)
            )

    moods = [e.mood for e in entries if e.mood is not None]
    energies = [e.energy for e in entries if e.energy is not None]

    return jsonify({
        "total_entries": count,
        "earliest_date": first.isoformat() if first else None,
        "latest_date": last.isoformat() if last else None,
        "avg_mood_30d": round(sum(moods) / len(moods), 1) if moods else None,
        "avg_energy_30d": round(sum(energies) / len(energies), 1) if energies else None,
        "entries_30d": len(entries),
    })


# ── Config ───────────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET", "PUT"])
def handle_config():
    if request.method == "PUT":
        body = request.get_json(silent=True) or {}
        ai = body.get("ai", {})
        if "openai_api_key" in ai:
            cfg.ai.openai_api_key = ai["openai_api_key"]
        if "anthropic_api_key" in ai:
            cfg.ai.anthropic_api_key = ai["anthropic_api_key"]
        if "gemini_api_key" in ai:
            cfg.ai.gemini_api_key = ai["gemini_api_key"]
        if "enabled" in ai:
            cfg.ai.enabled = bool(ai["enabled"])
        if "provider" in ai:
            cfg.ai.provider = ai["provider"]
        if "base_url" in ai:
            cfg.ai.base_url = ai["base_url"]
        if "model" in ai:
            cfg.ai.model = ai["model"]
        cfg_module.save(cfg)
        return jsonify({"ok": True})

    return jsonify({
        "ai": {
            "enabled": cfg.ai.enabled,
            "provider": cfg.ai.provider,
            "model": cfg.ai.model,
            "base_url": cfg.ai.base_url,
            "has_openai_key": bool(cfg.ai.openai_api_key),
            "has_anthropic_key": bool(cfg.ai.anthropic_api_key),
            "has_gemini_key": bool(cfg.ai.gemini_api_key),
        }
    })


# ── Export / Import ──────────────────────────────────────────────────────────

@app.route("/api/export", methods=["GET"])
def export_entries():
    fmt = request.args.get("format", "json").strip().lower()
    agent = request.args.get("agent", "").strip()

    with _db() as database:
        if agent:
            entries = db_module.list_entries(database, limit=100000, agent_id=agent)
        else:
            entries = db_module.list_entries(database, limit=100000)

    if fmt == "html":
        return _export_html(entries)
    elif fmt == "markdown":
        return _export_markdown(entries)
    else:
        return jsonify([_entry_dict(e) for e in entries])


def _export_html(entries: list[Entry]) -> Response:
    lines = [
        "<!DOCTYPE html><html><head><meta charset='UTF-8'>",
        "<title>Speculae Export</title>",
        "<style>body{font-family:Georgia,serif;max-width:700px;margin:2rem auto;padding:0 1rem;color:#1f1812;line-height:1.7}",
        "h1{font-size:2rem;margin-bottom:0.5rem}h2{font-size:1.2rem;color:#7a2e2e;margin-top:2rem}",
        ".meta{font-size:0.85rem;color:#8a7d6a;margin-bottom:1rem}",
        ".content{margin-bottom:2rem;padding-bottom:1rem;border-bottom:1px solid #d4c8b0}",
        "code{font-family:'JetBrains Mono',monospace;background:#ebe2d1;padding:2px 5px;font-size:0.9em}",
        "pre{background:#ebe2d1;padding:1rem;overflow-x:auto}pre code{background:none;padding:0}",
        "blockquote{border-left:3px solid #7a2e2e;padding-left:1rem;color:#4a3f33;font-style:italic}",
        "</style></head><body>",
        "<h1>Speculae Journal Export</h1>",
        f"<p class='meta'>{len(entries)} entries · exported {date.today().isoformat()}</p>",
    ]
    for e in reversed(entries):
        lines.append(f"<h2>{e.date.strftime('%A, %d %B %Y')}</h2>")
        meta_parts = []
        if e.mood:
            meta_parts.append(f"mood: {e.mood}/5")
        if e.energy:
            meta_parts.append(f"energy: {e.energy}/5")
        if e.tags:
            meta_parts.append("tags: " + ", ".join(e.tags))
        if e.starred:
            meta_parts.append("★ starred")
        if meta_parts:
            lines.append(f"<p class='meta'>{' · '.join(meta_parts)}</p>")
        if e.content.strip():
            import html
            content = html.escape(e.content)
            # Basic markdown-ish rendering
            content = content.replace("\n\n", "</p><p>")
            content = content.replace("\n", "<br>")
            lines.append(f"<div class='content'><p>{content}</p></div>")
    lines.append("</body></html>")
    body = "\n".join(lines)
    return Response(body, mimetype="text/html",
                    headers={"Content-Disposition": "attachment; filename=speculae-export.html"})


def _export_markdown(entries: list[Entry]) -> Response:
    lines = ["# Speculae Journal Export\n"]
    for e in reversed(entries):
        lines.append(f"## {e.date.strftime('%A, %d %B %Y')}\n")
        meta = []
        if e.mood:
            meta.append(f"mood: {e.mood}/5")
        if e.energy:
            meta.append(f"energy: {e.energy}/5")
        if e.tags:
            meta.append("tags: " + ", ".join(e.tags))
        if e.starred:
            meta.append("★ starred")
        if meta:
            lines.append(f"*{' · '.join(meta)}*\n")
        if e.content.strip():
            lines.append(e.content.strip() + "\n")
        lines.append("---\n")
    body = "\n".join(lines)
    return Response(body, mimetype="text/markdown",
                    headers={"Content-Disposition": "attachment; filename=speculae-export.md"})


@app.route("/api/import", methods=["POST"])
def import_entries():
    body = request.get_json(silent=True)
    if not isinstance(body, list):
        return jsonify({"error": "Expected a JSON array of entries"}), 400

    imported = 0
    with _db() as database:
        for item in body:
            try:
                entry_date = date.fromisoformat(item["date"])
            except (KeyError, ValueError):
                continue
            entry = Entry(
                id=item.get("id"),
                date=entry_date,
                content=item.get("content", ""),
                mood=int(item["mood"]) if item.get("mood") else None,
                energy=int(item["energy"]) if item.get("energy") else None,
                tags=item.get("tags", []),
                starred=bool(item.get("starred", False)),
                agent_id=item.get("agent_id"),
            )
            db_module.save_entry(database, entry)
            imported += 1

    return jsonify({"imported": imported})


# ── Agent API ────────────────────────────────────────────────────────────────

@app.route("/api/agents", methods=["GET"])
def list_agents():
    with _db() as database:
        agents = db_module.list_agents_detailed(database)
    return jsonify(agents)


@app.route("/api/agents/<agent_id>/entries", methods=["GET"])
def agent_list_entries(agent_id: str):
    try:
        limit = int(request.args.get("limit", 100))
        if not (1 <= limit <= 10000):
            return jsonify({"error": "limit must be between 1 and 10000"}), 400
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

    since_str = request.args.get("since")
    until_str = request.args.get("until")
    try:
        since = date.fromisoformat(since_str) if since_str else None
    except ValueError:
        return jsonify({"error": "since must be a date in YYYY-MM-DD format"}), 400
    try:
        until = date.fromisoformat(until_str) if until_str else None
    except ValueError:
        return jsonify({"error": "until must be a date in YYYY-MM-DD format"}), 400

    starred_only = request.args.get("starred", "").strip().lower() == "true"

    with _db() as database:
        entries = db_module.list_entries(
            database,
            limit=limit,
            since=since,
            until=until,
            starred_only=starred_only,
            agent_id=agent_id,
        )

    return jsonify([_entry_dict(e) for e in entries])


@app.route("/api/agents/<agent_id>/entries", methods=["POST"])
def agent_create_entry(agent_id: str):
    body = request.get_json(silent=True) or {}

    try:
        entry_date = date.fromisoformat(body.get("date", date.today().isoformat()))
    except ValueError:
        return jsonify({"error": "invalid date — use YYYY-MM-DD"}), 400

    tags = _parse_tags(body)
    if tags is None:
        return jsonify({"error": "'tags' must be a list of strings"}), 400

    entry = Entry(
        date=entry_date,
        content=body.get("content", ""),
        mood=_valid_mood_energy(body.get("mood")),
        energy=_valid_mood_energy(body.get("energy")),
        tags=tags,
        starred=bool(body.get("starred", False)),
        agent_id=agent_id,
    )

    with _db() as database:
        saved = db_module.save_entry(database, entry)

    return jsonify(_entry_dict(saved))


@app.route("/api/agents/<agent_id>/entries/<entry_id>", methods=["GET"])
def agent_get_entry(agent_id: str, entry_id: str):
    with _db() as database:
        entry = db_module.get_entry_by_id(database, entry_id)
    if not entry or entry.agent_id != agent_id:
        return jsonify({"error": "not found"}), 404
    return jsonify(_entry_dict(entry))


@app.route("/api/agents/<agent_id>/entries/<entry_id>", methods=["PUT"])
def agent_update_entry(agent_id: str, entry_id: str):
    with _db() as database:
        entry = db_module.get_entry_by_id(database, entry_id)
        if not entry or entry.agent_id != agent_id:
            return jsonify({"error": "not found"}), 404

        body = request.get_json(silent=True) or {}
        if "content" in body:
            entry.content = body["content"]
        if "mood" in body:
            entry.mood = _valid_mood_energy(body["mood"])
        if "energy" in body:
            entry.energy = _valid_mood_energy(body["energy"])
        if "tags" in body:
            entry.tags = [t.strip() for t in body["tags"] if t.strip()]
        if "starred" in body:
            entry.starred = bool(body["starred"])

        saved = db_module.save_entry(database, entry)

    return jsonify(_entry_dict(saved))


@app.route("/api/agents/<agent_id>/entries/<entry_id>", methods=["DELETE"])
def agent_delete_entry(agent_id: str, entry_id: str):
    with _db() as database:
        entry = db_module.get_entry_by_id(database, entry_id)
        if not entry or entry.agent_id != agent_id:
            return jsonify({"error": "not found"}), 404
        db_module.delete_images_for_entry(database, entry_id)
        ok = db_module.delete_entry(database, entry_id)

    return jsonify({"deleted": ok})


@app.route("/api/agents/<agent_id>/stats", methods=["GET"])
def agent_stats(agent_id: str):
    with _db() as database:
        entries = db_module.list_entries(database, limit=10000, agent_id=agent_id)

    moods = [e.mood for e in entries if e.mood is not None]
    energies = [e.energy for e in entries if e.energy is not None]
    all_tags = {}
    for e in entries:
        for t in e.tags:
            all_tags[t] = all_tags.get(t, 0) + 1
    top_tags = sorted(all_tags.items(), key=lambda x: -x[1])[:10]

    return jsonify({
        "total_entries": len(entries),
        "earliest_date": min((e.date.isoformat() for e in entries), default=None),
        "latest_date": max((e.date.isoformat() for e in entries), default=None),
        "avg_mood": round(sum(moods) / len(moods), 1) if moods else None,
        "avg_energy": round(sum(energies) / len(energies), 1) if energies else None,
        "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
    })


# ── Wellness ─────────────────────────────────────────────────────────────────


@app.route("/api/wellness/breathing", methods=["GET"])
def list_breathing():
    exercises = wellness_module.get_exercises()
    return jsonify({
        k: {"name": v.name, "description": v.description, "total_seconds": v.total_seconds}
        for k, v in exercises.items()
    })


@app.route("/api/wellness/breathing/<name>", methods=["GET"])
def get_breathing(name: str):
    ex = wellness_module.get_exercise(name)
    if not ex:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "name": ex.name,
        "description": ex.description,
        "pattern": [{"action": a, "duration": d} for a, d in ex.pattern],
        "cycles": ex.cycles,
        "total_seconds": ex.total_seconds,
    })


@app.route("/api/wellness/prompt", methods=["GET"])
def get_prompt():
    import random as _random
    category = request.args.get("category", "").strip()
    if category:
        prompts = wellness_module.PROMPTS.get(category)
        if prompts:
            prompt = _random.choice(prompts)
            return jsonify({"prompt": prompt, "category": category})
    # Random from all
    all_cats = wellness_module.get_categories()
    cat = _random.choice(all_cats)
    prompts = wellness_module.PROMPTS[cat]
    prompt = _random.choice(prompts)
    return jsonify({"prompt": prompt, "category": cat})


@app.route("/api/wellness/prompt/daily", methods=["GET"])
def get_daily_prompt():
    prompt, cat = wellness_module.get_daily_prompt()
    today = date.today().isoformat()
    return jsonify({"prompt": prompt, "category": cat, "date": today})


@app.route("/api/wellness/meditation/presets", methods=["GET"])
def meditation_presets():
    return jsonify(wellness_module.MEDITATION_PRESETS)


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    cfg_module.ensure_dirs(cfg)
    url = f"http://{HOST}:{PORT}"
    print(f"\n  o  speculae v{VERSION} . web interface")
    print(f"  {'-' * 29}")
    print(f"  {url}")
    print("\n  your journal stays on your machine")
    # Only open the system browser when running as a CLI command.
    # When bundled as a PyInstaller sidecar inside the Tauri desktop app,
    # skip this — the Tauri WebView2 window is already the browser.
    if not getattr(sys, 'frozen', False):
        print("  ctrl+c to stop\n")
        webbrowser.open(url)
    else:
        print("  running as desktop sidecar\n")
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
