"""Burst-capture a Generic profile off the emulator window, then judge it.

Generic sets FLAG_SECURE, so Android-side capture (adb screencap, scrcpy) returns
black. Capturing at the compositor level instead — KWin already has the
emulator's rendered pixels on screen — sidesteps that entirely. No ADB, no input
automation: you scroll, this only reads the screen.

    .venv/bin/python grab.py              # 12s burst, dedupe, judge, print verdict
    .venv/bin/python grab.py -s 20        # longer burst for a long profile
    .venv/bin/python grab.py --no-judge   # just capture, judge later

Scroll the profile top-to-bottom while it runs. Near-identical consecutive
frames (you paused, or scrolled past the capture tick) are dropped, so what
reaches the judge is one frame per distinct screenful.

KDE/Wayland only — uses `spectacle -b -n -a` (active window). Keep the emulator
focused for the whole burst.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

import config

# Frames are "the same screenful" below this Hamming distance on a 16x16
# average hash. Scrolling moves well past it; a paused screen doesn't.
_DUPE_THRESHOLD = 8
_HASH_EDGE = 16
_MAX_FRAMES = 12  # judge_profile's own ceiling


def _ahash(path: Path) -> int:
    """Average hash — cheap, and we only need 'did the screen change'."""
    with Image.open(path) as im:
        px = im.convert("L").resize((_HASH_EDGE, _HASH_EDGE), Image.LANCZOS).tobytes()
    mean = sum(px) / len(px)
    bits = 0
    for i, p in enumerate(px):
        if p > mean:
            bits |= 1 << i
    return bits


def _capture(dest: Path) -> bool:
    """One active-window grab via KWin. False if spectacle wrote nothing."""
    try:
        subprocess.run(
            ["spectacle", "-b", "-n", "-a", "-o", str(dest)],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  capture failed: {e}", file=sys.stderr)
        return False
    # spectacle writes asynchronously; give the file a moment to land.
    for _ in range(20):
        if dest.exists() and dest.stat().st_size > 0:
            return True
        time.sleep(0.1)
    return False


def burst(seconds: float, interval: float, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    kept: list[Path] = []
    last_hash: int | None = None
    scratch = Path(tempfile.mkdtemp(prefix="generic-grab-"))

    print(f"capturing for {seconds:.0f}s — scroll the profile now")
    deadline = time.monotonic() + seconds
    n = 0
    while time.monotonic() < deadline and len(kept) < _MAX_FRAMES:
        n += 1
        shot = scratch / f"raw_{n:03d}.png"
        if not _capture(shot):
            time.sleep(interval)
            continue

        h = _ahash(shot)
        if last_hash is not None and bin(h ^ last_hash).count("1") < _DUPE_THRESHOLD:
            shot.unlink(missing_ok=True)  # same screenful as the last keeper
        else:
            dest = out_dir / f"{len(kept) + 1:02d}.png"
            shot.replace(dest)
            kept.append(dest)
            last_hash = h
            print(f"  [{len(kept)}] {dest.name}")

        time.sleep(interval)

    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-s", "--seconds", type=float, default=12.0)
    ap.add_argument("-i", "--interval", type=float, default=1.2)
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()

    out = args.out or config.BASE_DIR / "shots" / time.strftime("%Y%m%d-%H%M%S")
    frames = burst(args.seconds, args.interval, out)

    if not frames:
        print("nothing captured — is the emulator the active window?", file=sys.stderr)
        sys.exit(1)

    print(f"\n{len(frames)} distinct frames -> {out}")
    if args.no_judge:
        return

    import db
    import generic_mcp

    db.init_db()
    print("judging...\n")
    r = generic_mcp.judge_profile([str(f) for f in frames])

    print(f"  {r['decision'].upper()}  (#{r['decision_id']})")
    print(f"  {r['reasoning']}")
    if r["draft_message"]:
        print(f"\n  respond to: {r['target_prompt']}")
        print(f"  draft: {r['draft_message']}")
    print(
        f"\nafter you act, record it:\n"
        f"  record_outcome({r['decision_id']}, 'liked'|'skipped')\n"
        f"  record_sent_message({r['decision_id']}, '<what you actually sent>', was_edited)"
    )


if __name__ == "__main__":
    main()
