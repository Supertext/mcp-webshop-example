import json
import sqlite3
import stat
import subprocess

import pytest

from scripts.make_stage import ROOT, StageError, build


def _git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture(scope="module")
def stage(tmp_path_factory):
    env = tmp_path_factory.mktemp("env") / ".env"
    env.write_text("SUPERTEXT_API_KEY=test-token\n")
    env.chmod(0o600)
    dest = tmp_path_factory.mktemp("parent") / "firn-stage"
    build(dest, env_file=env)
    return dest


def test_stage_copy_holds_the_shop_but_not_the_demo_notes_or_tests(stage):
    assert (stage / "app" / "main.py").exists()
    assert (stage / "CLAUDE.md").exists()
    for left_out in ("docs", "tests", "README.md", "scripts/make_stage.py"):
        assert not (stage / left_out).exists(), left_out


def test_stage_git_history_has_nothing_to_dig_up(stage):
    """A clone would carry every past commit, docs included. The stage copy has
    exactly one commit, no remote, and has never tracked docs/ or tests/."""
    assert _git(stage, "rev-list", "--all", "--count").strip() == "1"
    assert _git(stage, "remote").strip() == ""
    ever_tracked = _git(stage, "log", "--all", "--name-only", "--format=").split()
    assert ever_tracked
    assert not [p for p in ever_tracked if p.startswith(("docs/", "tests/"))]


def test_nothing_in_the_stage_copy_points_at_what_was_left_out(stage):
    """A dangling reference to a missing design doc invites an agent to go
    looking for it, including outside the folder."""
    hits = subprocess.run(
        ["grep", "-rIl", "-E", r"docs/|tests/|RUN_OF_SHOW|DESIGN\.md",
         "--exclude-dir=.git", str(stage)],
        capture_output=True, text=True,
    ).stdout
    assert hits == ""


def test_stage_copy_is_reset_and_committed_clean(stage):
    for locale in ("de-CH", "fr-CH", "it-CH"):
        catalogue = json.loads((stage / "locales" / f"{locale}.json").read_text())
        assert catalogue["strings"] == {}
    ledger = json.loads((stage / "data" / "verification_ledger.json").read_text())
    assert ledger["orders"] == []
    db = sqlite3.connect(stage / "data" / "analytics.sqlite")
    assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] > 0
    assert list((stage / "app" / "static" / "img").glob("*.svg"))
    assert _git(stage, "status", "--porcelain") == ""


def test_stage_carries_the_api_key_file_privately(stage):
    env = stage / ".env"
    assert env.read_text() == "SUPERTEXT_API_KEY=test-token\n"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_stage_rebuilds_its_own_previous_copy(tmp_path):
    dest = tmp_path / "firn-stage"
    build(dest, env_file=None)
    (dest / "leftover.txt").write_text("from the last show")

    build(dest, env_file=None)

    assert not (dest / "leftover.txt").exists()
    assert (dest / "app" / "main.py").exists()


def test_stage_refuses_to_replace_a_folder_it_did_not_build(tmp_path):
    dest = tmp_path / "precious"
    dest.mkdir()
    (dest / "notes.txt").write_text("keep me")

    with pytest.raises(StageError):
        build(dest, env_file=None)

    assert (dest / "notes.txt").read_text() == "keep me"


def test_stage_refuses_a_destination_inside_the_repo():
    dest = ROOT / "firn-stage-inside"

    with pytest.raises(StageError):
        build(dest, env_file=None)

    assert not dest.exists()
