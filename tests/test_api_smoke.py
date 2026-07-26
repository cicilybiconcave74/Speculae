#!/usr/bin/env python3
"""Smoke test for all Speculae API endpoints — runs as pytest tests."""
import sys
import base64
import pytest

sys.path.insert(0, "src")

from speculae.web.server import app, cfg


@pytest.fixture
def client(tmp_path):
    cfg.db_file = tmp_path / "test_api_journal.db"
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestEntries:
    def test_list_entries(self, client):
        r = client.get("/api/entries?days=30")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_get_entries_for_date(self, client):
        r = client.get("/api/entries/2026-07-21")
        assert r.status_code == 200

    def test_create_entry(self, client):
        r = client.post("/api/entries/2026-07-21", json={
            "content": "Smoke test", "mood": 4, "energy": 3, "tags": ["test"]
        })
        assert r.status_code == 200
        assert "id" in r.get_json()

    def test_star_toggle(self, client):
        r = client.post("/api/entries/2026-07-21", json={"content": "star test"})
        eid = r.get_json()["id"]
        r = client.put(f"/api/entries/{eid}", json={"starred": True})
        assert r.status_code == 200
        assert r.get_json()["starred"] is True

    def test_starred_filter(self, client):
        r = client.get("/api/entries?starred=true")
        assert r.status_code == 200

    def test_tag_filter(self, client):
        r = client.get("/api/entries?tag=test")
        assert r.status_code == 200

    def test_mood_filter(self, client):
        r = client.get("/api/entries?mood=4")
        assert r.status_code == 200

    def test_delete_entry(self, client):
        r = client.post("/api/entries/2026-07-21", json={"content": "delete me"})
        eid = r.get_json()["id"]
        r = client.delete(f"/api/entries/{eid}")
        assert r.status_code == 200
        assert r.get_json()["deleted"] is True

    def test_delete_entries_batch(self, client):
        r1 = client.post("/api/entries/2026-07-21", json={"content": "batch 1"})
        r2 = client.post("/api/entries/2026-07-21", json={"content": "batch 2"})
        id1 = r1.get_json()["id"]
        id2 = r2.get_json()["id"]
        r = client.delete("/api/entries/batch", json={"ids": [id1, id2]})
        assert r.status_code == 200
        assert r.get_json()["deleted_count"] == 2


class TestCalendar:
    def test_calendar(self, client):
        r = client.get("/api/calendar?months=3")
        assert r.status_code == 200

    def test_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        assert "total_entries" in r.get_json()


class TestPatternsInsights:
    def test_patterns(self, client):
        r = client.get("/api/patterns")
        assert r.status_code == 200

    def test_insights(self, client):
        r = client.get("/api/insights")
        assert r.status_code == 200

    def test_insights_excludes_agent_entries_by_default(self, client):
        from datetime import date as _date
        today = _date.today().isoformat()
        client.post(f"/api/entries/{today}", json={
            "content": "human journal", "mood": 5, "tags": ["human-tag"],
        })
        client.post("/api/agents/test-bot/entries", json={
            "content": "agent log", "mood": 1, "date": today, "tags": ["agent-tag"],
        })
        r = client.get("/api/insights?refresh=true")
        assert r.status_code == 200
        content = r.get_json()["content"]
        assert "human-tag" in content
        assert "agent-tag" not in content

    def test_insights_agent_scope(self, client):
        from datetime import date as _date
        today = _date.today().isoformat()
        client.post(f"/api/entries/{today}", json={
            "content": "human only", "tags": ["human-tag"],
        })
        client.post("/api/agents/insight-bot/entries", json={
            "content": "agent only", "mood": 4, "date": today, "tags": ["agent-tag"],
        })
        r = client.get("/api/insights?agent=insight-bot&refresh=true")
        assert r.status_code == 200
        content = r.get_json()["content"]
        assert "agent-tag" in content
        assert "human-tag" not in content


class TestConfig:
    def test_get_config(self, client):
        r = client.get("/api/config")
        assert r.status_code == 200
        assert "ai" in r.get_json()


class TestExportImport:
    def test_export_json(self, client):
        r = client.get("/api/export?format=json")
        assert r.status_code == 200

    def test_export_html(self, client):
        r = client.get("/api/export?format=html")
        assert r.status_code == 200
        assert "text/html" in r.content_type

    def test_export_markdown(self, client):
        r = client.get("/api/export?format=markdown")
        assert r.status_code == 200

    def test_import(self, client):
        r = client.post("/api/import", json=[
            {"date": "2026-07-20", "content": "Imported", "mood": 3}
        ])
        assert r.status_code == 200
        assert r.get_json()["imported"] >= 1


class TestWellness:
    def test_breathing_list(self, client):
        r = client.get("/api/wellness/breathing")
        assert r.status_code == 200
        assert len(r.get_json()) == 4

    def test_breathing_exercise(self, client):
        r = client.get("/api/wellness/breathing/box")
        assert r.status_code == 200
        assert "pattern" in r.get_json()

    def test_breathing_not_found(self, client):
        r = client.get("/api/wellness/breathing/nonexistent")
        assert r.status_code == 404

    def test_prompt(self, client):
        r = client.get("/api/wellness/prompt")
        assert r.status_code == 200
        assert "prompt" in r.get_json()

    def test_prompt_by_category(self, client):
        r = client.get("/api/wellness/prompt?category=gratitude")
        assert r.status_code == 200
        assert r.get_json()["category"] == "gratitude"

    def test_daily_prompt(self, client):
        r = client.get("/api/wellness/prompt/daily")
        assert r.status_code == 200
        assert "date" in r.get_json()

    def test_meditation_presets(self, client):
        r = client.get("/api/wellness/meditation/presets")
        assert r.status_code == 200
        assert len(r.get_json()) == 5


class TestAgents:
    def test_list_agents(self, client):
        r = client.get("/api/agents")
        assert r.status_code == 200

    def test_agent_create_entry(self, client):
        r = client.post("/api/agents/aurora/entries", json={
            "content": "Agent test", "mood": 5, "tags": ["agent-test"]
        })
        assert r.status_code == 200
        assert r.get_json()["agent_id"] == "aurora"

    def test_agent_list_entries(self, client):
        r = client.get("/api/agents/aurora/entries")
        assert r.status_code == 200

    def test_agent_stats(self, client):
        r = client.get("/api/agents/aurora/stats")
        assert r.status_code == 200

    def test_agent_wrong_agent_404(self, client):
        r = client.post("/api/agents/test/entries", json={"content": "x"})
        eid = r.get_json()["id"]
        r = client.get(f"/api/agents/wrong/entries/{eid}")
        assert r.status_code == 404

    def test_agent_delete(self, client):
        r = client.post("/api/agents/test/entries", json={"content": "del"})
        eid = r.get_json()["id"]
        r = client.delete(f"/api/agents/test/entries/{eid}")
        assert r.status_code == 200
        assert r.get_json()["deleted"] is True

    def test_stats_with_agent_filter(self, client):
        r = client.get("/api/stats?agent=aurora")
        assert r.status_code == 200


class TestImages:
    def test_upload_image(self, client):
        r = client.post("/api/entries/2026-07-21", json={"content": "img test"})
        eid = r.get_json()["id"]
        img_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100).decode()
        r = client.post(f"/api/entries/{eid}/images", json={
            "data": img_b64, "filename": "test.png", "mime_type": "image/png"
        })
        assert r.status_code == 200
        assert "id" in r.get_json()

    def test_list_images(self, client):
        r = client.get("/api/entries/2026-07-21/images")
        assert r.status_code == 200

    def test_list_images_does_not_return_blob_data(self, client):
        r = client.post("/api/entries/2026-07-21", json={"content": "blob test"})
        eid = r.get_json()["id"]
        img_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\xff" * 200).decode()
        client.post(f"/api/entries/{eid}/images", json={
            "data": img_b64, "filename": "blob.png", "mime_type": "image/png",
        })
        r = client.get(f"/api/entries/{eid}/images")
        assert r.status_code == 200
        items = r.get_json()
        assert len(items) == 1
        assert "data" not in items[0]
        r2 = client.get(f"/api/images/{items[0]['id']}")
        assert r2.status_code == 200
        assert len(r2.data) > 0

    def test_serve_image(self, client):
        r = client.post("/api/entries/2026-07-21", json={"content": "img2"})
        eid = r.get_json()["id"]
        img_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        r = client.post(f"/api/entries/{eid}/images", json={
            "data": img_b64, "filename": "t.png", "mime_type": "image/png"
        })
        img_id = r.get_json()["id"]
        r = client.get(f"/api/images/{img_id}")
        assert r.status_code == 200
        assert "image" in r.content_type

    def test_delete_image(self, client):
        r = client.post("/api/entries/2026-07-21", json={"content": "img3"})
        eid = r.get_json()["id"]
        img_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        r = client.post(f"/api/entries/{eid}/images", json={
            "data": img_b64, "filename": "d.png", "mime_type": "image/png"
        })
        img_id = r.get_json()["id"]
        r = client.delete(f"/api/images/{img_id}")
        assert r.status_code == 200
        assert r.get_json()["deleted"] is True
