#!/usr/bin/env python3
"""Fetch and install the latest release wheel from GitHub via pipx."""

import json
import subprocess
import sys
import urllib.request

OWNER_REPO = "brownbat/kingdom-clicker"
API_URL = f"https://api.github.com/repos/{OWNER_REPO}/releases/latest"


def fetch_latest_wheel() -> str:
    with urllib.request.urlopen(API_URL, timeout=5) as resp:
        data = json.load(resp)
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".whl"):
            return asset["browser_download_url"]
    raise SystemExit("No wheel asset found in latest release.")


def install_with_pipx(url: str) -> None:
    cmd = ["pipx", "install", "--force", url]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)


def main() -> None:
    try:
        wheel_url = fetch_latest_wheel()
    except Exception as exc:
        raise SystemExit(f"Failed to fetch latest release: {exc}")

    print("Latest wheel URL:", wheel_url)
    if "--print-only" in sys.argv:
        return

    try:
        install_with_pipx(wheel_url)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)


if __name__ == "__main__":
    main()
