"""Judge local profile screenshots without an MCP client.

Usage:
    .venv/bin/python judge.py path/to/01.png path/to/02.png
    .venv/bin/python judge.py --app like_comment shots/profile/*.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import apps as app_catalog
import db
import dating_mcp
from llm.base import LANES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_paths", nargs="+", type=Path)
    parser.add_argument("--app", default="generic", help="profile format")
    args = parser.parse_args()

    db.init_db()
    result = dating_mcp.judge_profile(
        [str(path) for path in args.image_paths], app=app_catalog.normalize(args.app)
    )
    print(f"{result['decision'].upper()}  (#{result['decision_id']})")
    print(result["reasoning"])
    if not result["draft_message"]:
        return
    lane = LANES.get(result["draft_lane"], "")
    print(f"\nrespond to: {result['target_prompt']}")
    print(f"draft: {result['draft_message']}" + (f"  [{lane}]" if lane else ""))
    for number, alternative in enumerate(result["alternatives"], 1):
        print(f"\nbackup {number}: {alternative['message']}")


if __name__ == "__main__":
    main()
