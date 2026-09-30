import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app
from scripts.seed_analytics import seed

client = TestClient(app)


@pytest.fixture(autouse=True)
def seeded_db(tmp_path, monkeypatch):
    """Ruling C5: dashboard tests read a seeded tmp DB, never data/analytics.sqlite.

    connect()'s default path is bound at definition time, so patching
    app.analytics.DB_PATH would NOT redirect it — patch main.connect instead.
    /admin is excluded from tracking (ruling C3), so these tests neither read
    nor write the live DB.
    """
    db = tmp_path / "analytics.sqlite"
    seed(db)
    real_connect = main.connect
    monkeypatch.setattr(main, "connect", lambda *a, **k: real_connect(db))


def test_dashboard_renders():
    response = client.get("/admin/analytics")
    assert response.status_code == 200


def test_dashboard_shows_locale_rows_and_paths():
    text = client.get("/admin/analytics").text
    assert "de-CH" in text
    assert "fr-CH" in text
    assert "/p/" in text


def test_dashboard_is_not_localised():
    """It is an internal tool, so it stays English in every locale."""
    text = client.get("/fr-CH/admin/analytics").text
    assert 'lang="fr-CH"' in text
    assert "Conversion" in text
