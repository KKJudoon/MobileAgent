#!/usr/bin/env python3
"""Local command for the API-only Mobile-Agent-v3.5 phone runner."""
import argparse
import json
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "Mobile-Agent-v3.5" / "mobile_use"


def load_environment():
    config = Path(os.environ.get("MOBILE_AGENT_ENV_FILE", str(ROOT / ".env"))).expanduser()
    if config.is_file():
        if config.stat().st_mode & 0o077:
            raise SystemExit("The API configuration must be private: chmod 600 " + str(config))
        for raw in config.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, value = line.partition("=")
            if not sep or name not in {
                "MOBILE_AGENT_API_KEY", "DASHSCOPE_API_KEY", "MOBILE_AGENT_BASE_URL",
                "MOBILE_AGENT_MODEL", "MOBILE_AGENT_DEVICE", "MOBILE_AGENT_ADB",
            }:
                raise SystemExit("Unsupported API configuration entry")
            parts = shlex.split(value, comments=True)
            if len(parts) > 1:
                raise SystemExit("Quote configuration values that contain spaces")
            os.environ.setdefault(name, parts[0] if parts else "")


def devices(adb):
    result = subprocess.run([adb, "devices"], check=True, capture_output=True,
                            text=True, timeout=15)
    return [line.split()[0] for line in result.stdout.splitlines()[1:]
            if len(line.split()) == 2 and line.split()[1] == "device"]


def main():
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Read installation, device and API readiness")
    capture = commands.add_parser("capture", help="Capture the phone screen without changing its UI")
    capture.add_argument("path", type=Path)
    run = commands.add_parser("run", help="Execute a phone task using the configured model API")
    run.add_argument("instruction")
    run.add_argument("--max-steps", type=int, default=30)
    run.add_argument("--add-info", default="")
    args = parser.parse_args()
    adb = shutil.which(os.environ.get("MOBILE_AGENT_ADB") or "adb")
    if not adb:
        mac_sdk_adb = Path.home() / "Library/Android/sdk/platform-tools/adb"
        if mac_sdk_adb.is_file():
            adb = str(mac_sdk_adb)
    if not adb:
        raise SystemExit("ADB was not found")
    online = devices(adb)
    device = os.environ.get("MOBILE_AGENT_DEVICE") or (online[0] if len(online) == 1 else None)
    api = bool(os.environ.get("MOBILE_AGENT_API_KEY") or os.environ.get("DASHSCOPE_API_KEY"))
    sys.path.insert(0, str(MOBILE))
    from utils import AdbTools
    if args.command == "doctor":
        keyboard = False
        screen = None
        if device in online:
            tools = AdbTools(adb, device)
            try:
                keyboard = bool(tools._run(["shell", "pm", "path", "com.android.adbkeyboard"]).stdout.strip())
            except subprocess.SubprocessError:
                pass
            screen = tools._run(["shell", "wm", "size"]).stdout.strip()
        print(json.dumps({"project_root": str(ROOT), "adb": adb, "device": device,
                          "device_online": device in online, "screen": screen,
                          "adb_keyboard_installed": keyboard, "api_configured": api,
                          "model": os.environ.get("MOBILE_AGENT_MODEL", "gui-plus-2026-02-26"),
                          "local_model_weights": False,
                          "ready_for_model_tasks": bool(api and keyboard and device in online)},
                         ensure_ascii=False, indent=2))
        return
    if device not in online:
        raise SystemExit("Configure MOBILE_AGENT_DEVICE with an authorized, connected phone")
    if args.command == "capture":
        args.path.parent.mkdir(parents=True, exist_ok=True)
        if not AdbTools(adb, device).get_screenshot(str(args.path)):
            raise SystemExit("Could not capture the phone screen")
        print(json.dumps({"path": str(args.path), "captured": True}))
        return
    if not api:
        raise SystemExit("Program installed; set MOBILE_AGENT_API_KEY or DASHSCOPE_API_KEY to run model tasks")
    os.chdir(ROOT)
    sys.argv = [str(MOBILE / "run_gui_owl_1_5_for_mobile.py"), "--adb_path", adb,
                "--device", device, "--instruction", args.instruction,
                "--max_steps", str(args.max_steps), "--add_info", args.add_info,
                "--output_dir", str(ROOT / "runs")]
    runpy.run_path(str(MOBILE / "run_gui_owl_1_5_for_mobile.py"), run_name="__main__")


if __name__ == "__main__":
    main()
