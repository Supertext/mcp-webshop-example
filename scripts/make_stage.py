"""Build a separate, clean copy of the shop to present from.

    make stage                          # ../firn-stage
    make stage STAGE_DIR=~/talks/firn   # anywhere outside this repository

The agent on stage explores the folder it is opened in, git history included,
and will read the run of show if it can find it. So the copy carries the tracked
files minus development material (docs/, tests/, README.md and this script),
this checkout's .env, a fresh one-commit history with no remote, and is reset
for the walk-on: locales empty, ledger clear, analytics seeded.

Rebuilding replaces a previous stage copy; any other existing folder is refused.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_DEST = ROOT.parent / "firn-stage"

# The run of show and design spec narrate what the analytics and the verifier
# will show; the tests and README point at them.
LEFT_OUT = ("docs/", "tests/", "README.md", "scripts/make_stage.py")

# Inside .git, so nothing in the working tree hints at how the copy was made.
MARKER = pathlib.Path(".git") / "firn-stage"

GIT_IDENTITY = (
    "-c", "user.name=Firn", "-c", "user.email=firn@example.invalid",
    "-c", "commit.gpgsign=false",
)


class StageError(Exception):
    """The destination is not safe to build into."""


def _git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout


def _clear_destination(dest: pathlib.Path) -> None:
    if dest == ROOT or ROOT in dest.parents:
        raise StageError(f"{dest} is inside this repository; pick a folder outside it")
    if not dest.exists():
        return
    if not (dest / MARKER).exists():
        raise StageError(f"{dest} exists and was not built by make stage; refusing to replace it")
    shutil.rmtree(dest)


def _copy_tracked_files(dest: pathlib.Path) -> None:
    for rel in _git(ROOT, "ls-files", "-z").split("\0"):
        if not rel or rel.startswith(LEFT_OUT):
            continue
        src = ROOT / rel
        if not src.exists():  # deleted in the working tree
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def build(
    dest: pathlib.Path = DEFAULT_DEST, *, env_file: pathlib.Path | None = ROOT / ".env"
) -> pathlib.Path:
    dest = pathlib.Path(dest).expanduser().resolve()
    _clear_destination(dest)

    dest.mkdir(parents=True)
    _git(dest, "init", "-q", "-b", "main")
    (dest / MARKER).write_text("built by make stage\n")

    _copy_tracked_files(dest)
    if env_file is not None and env_file.exists():
        shutil.copy2(env_file, dest / ".env")

    for script in ("scripts/gen_placeholders.py", "scripts/reset_demo.py"):
        subprocess.run([sys.executable, script], cwd=dest, check=True)

    _git(dest, "add", "-A")
    _git(dest, *GIT_IDENTITY, "commit", "-q", "--no-verify", "-m", "Firn")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a clean copy of the shop to present from.")
    parser.add_argument("--dest", type=pathlib.Path, default=DEFAULT_DEST)
    args = parser.parse_args()

    if not (ROOT / ".env").exists():
        print("warning: no .env here, so make quote and make translate will fail on stage",
              file=sys.stderr)
    try:
        dest = build(args.dest)
    except StageError as e:
        sys.exit(f"make stage: {e}")

    print(f"\nStage copy ready: {dest}")
    print(f"  cd {dest} && make run")
    print("  Open Claude Code in that folder, not in this checkout.")


if __name__ == "__main__":
    main()
