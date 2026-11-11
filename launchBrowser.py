"""将标题含 "360极速浏览器X" 的窗口左右分屏排列到工作区（仅 Windows）。"""

import os
from pathlib import Path
import subprocess
import sys

def launch_browser() -> int:
    """解析配置目录并启动浏览器。"""
    profileA = Path(".cdp-profile-360-a")
    profileB = Path(".cdp-profile-360-b")

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        print("ERROR: LOCALAPPDATA is not set", file=sys.stderr)
        return 1

    browser = Path(local_app_data) / "360ChromeX" / "Chrome" / "Application" / "360ChromeX.exe"
    if not browser.is_file():
        print(f"ERROR: 360ChromeX was not found at '{browser}'", file=sys.stderr)
        return 1

    subprocess.Popen(
        [
            str(browser), *[
                "--remote-debugging-port=9222",
                "--remote-debugging-address=127.0.0.1",
            ], f"--user-data-dir={Path(profileA)}", "about:newtab"],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
    subprocess.Popen(
        [
            str(browser), *[
                "--remote-debugging-port=9223",
                "--remote-debugging-address=127.0.0.1",
            ], f"--user-data-dir={Path(profileB)}", "about:newtab"],
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )

    print("360ChromeX started with CDP at http://127.0.0.1:9222 and http://127.0.0.1:9223")
    return 0


def main() -> None:
    launch_browser()


if __name__ == "__main__":
    main()