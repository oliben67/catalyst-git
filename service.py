#!/usr/bin/env python3
"""Poll a git repo's status and hash changed files until a stop signal is set.

Usage:
    git_status_hash_monitor.py <repo_path> <output_file> [stop_file] [--interval SECONDS]

Every cycle it runs `git status --porcelain` in <repo_path>, computes a
`git hash-object` for each listed file, and writes the result to
<output_file> as JSON: {"<filepath>": "<status_code>|<hash>", ...}.

Whenever a cycle's snapshot differs from the previous one, it also prints a
single JSON line to stdout describing exactly what changed since the last
cycle:
    {"entered": {path: "<status_code>|<hash>", ...},
     "updated": {path: {"from": "<old>", "to": "<new>"}, ...},
     "cleared": [path, ...]}
"entered" is a path that newly appears in `git status` (new, modified, or
deleted-but-uncommitted); "updated" is a path already pending whose content
hash changed again; "cleared" is a path that no longer appears in `git
status` (its pending change was committed or reverted). Cycles with no
difference print nothing, so a consumer can treat each stdout line as one
discrete change event.

The loop exits once stop_file's contents contain the word "stop"
(case-insensitive). stop_file defaults to "stop.signal" in the current
directory.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def parse_status_line(line):
    code = line[:2]
    filename = line[3:]
    if code[0] in ("R", "C") and " -> " in filename:
        filename = filename.split(" -> ", 1)[1]
    return code, filename


def hash_file(repo_path, filename):
    try:
        result = subprocess.run(
            ["git", "hash-object", filename],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def snapshot(repo_path):
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    entries = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        code, filename = parse_status_line(line)
        entries[filename] = f"{code}|{hash_file(repo_path, filename)}"
    return entries


def should_stop(stop_file):
    try:
        return "stop" in Path(stop_file).read_text().lower()
    except FileNotFoundError:
        return False


def diff_snapshots(previous, current):
    entered = {path: value for path, value in current.items() if path not in previous}
    updated = {
        path: {"from": previous[path], "to": value}
        for path, value in current.items()
        if path in previous and previous[path] != value
    }
    cleared = sorted(set(previous) - set(current))
    return entered, updated, cleared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo_path", help="Path to the root of the git project")
    parser.add_argument("output_file", help="Path to the JSON output file")
    parser.add_argument(
        "stop_file",
        nargs="?",
        default="stop.signal",
        help="File polled each cycle; loop stops when its contents contain "
        "'stop' (default: stop.signal)",
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="Seconds between polls (default: 60)"
    )
    args = parser.parse_args()

    previous = {}
    while True:
        entries = snapshot(args.repo_path)
        Path(args.output_file).write_text(json.dumps(entries, indent=2))

        entered, updated, cleared = diff_snapshots(previous, entries)
        if entered or updated or cleared:
            print(
                json.dumps({"entered": entered, "updated": updated, "cleared": cleared}),
                flush=True,
            )
        previous = entries

        if should_stop(args.stop_file):
            print("Stop signal received, exiting.")
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
