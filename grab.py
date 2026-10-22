"""Burst-capture a dating-app profile off the emulator/Waydroid window, then judge it.

Optional Linux/KWin helper — not the happy path (that's Telegram or MCP
with screenshots you already have). Some apps set FLAG_SECURE, so
Android-side capture returns black. Capturing at the compositor instead —
`spectacle -a` asks KWin for the active window's pixels.

Default (auto) mode: KWin focuses the Waydroid window, then adb scrolls
the focused app one screenful at a time. Pass --app so auto-scroll can
find the Android package. adb never likes, skips or types. --manual grabs
whatever window you focus.

    .venv/bin/python grab.py              # auto: focus, scroll, capture, judge
    .venv/bin/python grab.py --manual     # old way: you click in and scroll

Manual mode:

    .venv/bin/python grab.py --manual     # 3s to click in, 12s burst, judge
    .venv/bin/python grab.py -s 20        # longer burst for a long profile
    .venv/bin/python grab.py -l 6         # more time before capture starts
    .venv/bin/python grab.py --no-judge   # just capture, judge later

`-a` grabs whatever window has real focus, so there's a lead-in countdown —
click into the profile window during it. After that, scrolling by
click-dragging keeps it focused for the whole burst. Near-identical
consecutive frames (you paused, or scrolled past the capture tick) are
dropped, so what reaches the judge is one frame per distinct screenful.

KDE/Wayland only — uses `spectacle -b -n -a`.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

import apps as app_catalog
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


def _rows(path: Path) -> list[bytes]:
    """Small greyscale copy of the inside of the scrollable area (status
    bar, header, bottom nav, card edges and the like hearts cut off), as one
    bytes object per pixel row."""
    with Image.open(path) as im:
        w, h = im.size
        area = im.crop((int(w * 0.10), int(h * 0.10), int(w * 0.80), int(h * 0.80))).convert("L")
        area = area.resize((64, 160))
        data = area.tobytes()
    return [data[i * 64:(i + 1) * 64] for i in range(160)]


def _page_moved(prev: list[bytes], cur: list[bytes]) -> bool:
    """Did the page scroll between these two frames? A scroll shifts every
    row, so detailed rows almost never line up at the same height again. At
    the bottom of a profile the swipe does nothing, so most detailed rows
    stay put, even while a video prompt keeps playing in part of the screen.
    Plain rows (blank card backgrounds) are ignored since they match
    anywhere."""
    detailed = same = 0
    for a, b in zip(prev, cur):
        if max(a) - min(a) < 40:          # flat row, carries no position info
            continue
        detailed += 1
        if sum(abs(x - y) for x, y in zip(a, b)) / 64 < 2:
            same += 1
    # Tuned on real captures: scrolls score <= 0.07, a stuck page with a
    # playing video scores ~0.31.
    return detailed == 0 or same / detailed < 0.2


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


# ---------- auto mode: KWin focus + adb scroll ----------

_KWIN_FOCUS_JS = """
for (const w of workspace.windowList()) {
    if (w.resourceClass === "Waydroid") { workspace.activeWindow = w; break; }
}
"""


def _focus_waydroid() -> None:
    """Ask KWin to focus the Waydroid window, so `spectacle -a` grabs it
    without anyone clicking into it."""
    js = Path(tempfile.mkdtemp(prefix="dating-kwin-")) / "focus.js"
    js.write_text(_KWIN_FOCUS_JS)
    q = shutil.which("qdbus6") or "qdbus"
    name = "dating_grab_focus"
    try:
        sid = subprocess.run(
            [q, "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript",
             str(js), name],
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        subprocess.run([q, "org.kde.KWin", f"/Scripting/Script{sid}",
                        "org.kde.kwin.Script.run"], check=True, timeout=5)
    finally:
        subprocess.run([q, "org.kde.KWin", "/Scripting",
                        "org.kde.kwin.Scripting.unloadScript", name],
                       capture_output=True, timeout=5)
    time.sleep(0.5)


def _adb_serial() -> str:
    """Connect adb to the running Waydroid container and return its serial.
    The container IP comes from `waydroid status`, so a changed IP after a
    restart doesn't break this."""
    out = subprocess.run(["waydroid", "status"], capture_output=True,
                         text=True, timeout=10).stdout
    m = re.search(r"IP address:\s*(\S+)", out)
    if not m:
        raise SystemExit("waydroid session isn't running (no IP in `waydroid status`).")
    serial = f"{m.group(1)}:5555"
    subprocess.run(["adb", "connect", serial], capture_output=True, timeout=10)
    state = subprocess.run(["adb", "-s", serial, "get-state"], capture_output=True,
                           text=True, timeout=10)
    if state.stdout.strip() != "device":
        raise SystemExit(
            f"adb can't use {serial} ({(state.stderr or state.stdout).strip()}). "
            f"Accept the 'Allow USB debugging' popup in Waydroid, then retry."
        )
    return serial


def _adb(serial: str, *args: str) -> str:
    return subprocess.run(["adb", "-s", serial, "shell", *args], capture_output=True,
                          text=True, timeout=15).stdout


def _app_frame(serial: str, package: str) -> tuple[int, int, int, int]:
    """The app's window rect (left, top, right, bottom) in Android coordinates.
    Waydroid runs it as a freeform window, so it isn't the whole display."""
    dump = _adb(serial, "dumpsys", "window", "windows")
    block = dump.split(f"{package}/", 1)
    if len(block) < 2:
        raise SystemExit(
            f"{package} isn't open in Waydroid. Open a profile, then retry "
            f"(or use --manual to grab the focused window)."
        )
    m = re.search(r"frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\]", block[1])
    if not m:
        raise SystemExit("couldn't find the app window bounds via dumpsys.")
    left, top, right, bottom = map(int, m.groups())
    return left, top, right, bottom


def _scroll(serial: str, frame: tuple[int, int, int, int]) -> None:
    """One slow drag up through the middle of the app window: about half a
    screen, so consecutive frames overlap and no prompt gets cut between
    them. Slow on purpose so it doesn't fling. Starts above the skip button
    (bottom-left) and the nav bar, and stays clear of the like hearts on
    the right edge."""
    left, top, right, bottom = frame
    h = bottom - top
    x = left + (right - left) // 2
    y_from = top + int(h * 0.70)
    y_to = top + int(h * 0.22)
    _adb(serial, "input", "swipe", str(x), str(y_from), str(x), str(y_to), "600")


def auto_burst(out_dir: Path, settle: float, package: str) -> list[Path]:
    """Focus Waydroid, then capture, scroll, capture... until a scroll no
    longer changes the screen (bottom of the profile) or the frame cap."""
    serial = _adb_serial()
    frame = _app_frame(serial, package)
    _focus_waydroid()

    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="dating-grab-"))
    kept: list[Path] = []
    last_hash: int | None = None
    last_rows: list[bytes] | None = None
    print("auto-scrolling the profile...")
    for n in range(1, _MAX_FRAMES * 2):
        shot = scratch / f"raw_{n:03d}.png"
        if not _capture(shot):
            break
        h, rows = _ahash(shot), _rows(shot)
        same_frame = last_hash is not None and bin(h ^ last_hash).count("1") < _DUPE_THRESHOLD
        page_still = last_rows is not None and not _page_moved(last_rows, rows)
        if same_frame or page_still:
            print("  reached the bottom")
            break
        dest = out_dir / f"{len(kept) + 1:02d}.png"
        shutil.move(str(shot), str(dest))
        kept.append(dest)
        last_hash, last_rows = h, rows
        print(f"  [{len(kept)}] {dest.name}")
        if len(kept) >= _MAX_FRAMES:
            break
        _scroll(serial, frame)
        time.sleep(settle)
    return kept


def burst(seconds: float, interval: float, out_dir: Path, lead: float) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    kept: list[Path] = []
    last_hash: int | None = None
    scratch = Path(tempfile.mkdtemp(prefix="dating-grab-"))

    # -a grabs whatever window has real focus right now — which is this
    # terminal, not the profile. Give you time to click into it first.
    for remaining in range(int(lead), 0, -1):
        print(f"click into the profile window — capturing in {remaining}...")
        time.sleep(1)

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
            shutil.move(str(shot), str(dest))  # scratch is on tmpfs, out_dir isn't
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
    ap.add_argument("-l", "--lead", type=float, default=3.0,
                     help="seconds to click into the profile window before capture starts")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--manual", action="store_true",
                    help="you click in and scroll yourself (no adb)")
    ap.add_argument("--settle", type=float, default=0.9,
                    help="auto mode: seconds to let a scroll finish before capturing")
    ap.add_argument(
        "--app",
        default=config.DEFAULT_APP,
        help="dating app slug (generic/generic/generic/generic/generic)",
    )
    args = ap.parse_args()
    slug = app_catalog.normalize(args.app)

    out = args.out or config.BASE_DIR / "shots" / time.strftime("%Y%m%d-%H%M%S")
    if args.manual:
        frames = burst(args.seconds, args.interval, out, args.lead)
    else:
        package = app_catalog.PACKAGES.get(slug)
        if not package:
            raise SystemExit(
                f"auto-scroll has no Android package for {slug!r}; "
                f"use --manual or pick --app generic|generic|generic|generic"
            )
        frames = auto_burst(out, args.settle, package)

    if not frames:
        print("nothing captured", file=sys.stderr)
        sys.exit(1)

    print(f"\n{len(frames)} distinct frames -> {out}")
    if args.no_judge:
        return

    import db
    import dating_mcp
    from llm.base import LANES

    db.init_db()
    print("judging...\n")
    r = dating_mcp.judge_profile([str(f) for f in frames], app=slug)

    print(f"  {r['decision'].upper()}  (#{r['decision_id']})")
    print(f"  {r['reasoning']}")
    if r["draft_message"]:
        lane = LANES.get(r["draft_lane"], "")
        print(f"\n  respond to: {r['target_prompt']}")
        print(f"  draft: {r['draft_message']}" + (f"   [{lane}]" if lane else ""))
        for i, alt in enumerate(r["alternatives"], 1):
            print(f"\n  backup {i} -> {alt['target']}   [{LANES[alt['lane']]}]")
            print(f"  {alt['message']}")
    print(
        f"\nafter you act, record it:\n"
        f"  record_outcome({r['decision_id']}, 'liked'|'skipped')\n"
        f"  record_sent_message({r['decision_id']}, '<what you actually sent>', was_edited)"
    )


if __name__ == "__main__":
    main()
