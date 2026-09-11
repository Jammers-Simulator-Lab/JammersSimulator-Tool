#!/usr/bin/env python3
"""
Jammers Simulator Radio Localization & Neutralization CLI
"""

import argparse
import json
import os
import sys
from simulator_client import SimulatorClient

DEFAULT_ROBOT_ID = os.getenv("ROBOT_ID", "<YOUR_ROBOT_ID>")
DEFAULT_BASE_URL = os.getenv("SIMULATOR_URL", "http://127.0.0.1:2026")


def get_client(args) -> SimulatorClient:
    return SimulatorClient(base_url=args.base_url, robot_id=args.robot_id)


def handle_enter(args):
    client = get_client(args)
    res = client.enter()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("accepted"):
            print("✅ Arena Entered Successfully")
            print(f"   - Virtual Time: {res.get('virtual_time_s', 0)}s")
            print(f"   - Remaining Real Time: {res.get('remaining_real_duration_s', 0)}s")
            print(f"   - Max Virtual Time: {res.get('max_virtual_duration_s', 0)}s")
        else:
            print(f"❌ Enter Failed: {res}")
            sys.exit(1)


def handle_measure(args):
    client = get_client(args)
    res = client.measure(x=args.x, y=args.y, channel=args.channel)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("accepted"):
            result_type = res.get("measure_result")
            v_time = res.get("virtual_time_s", 0)
            dt = res.get("consumed_virtual_duration_s", 0)
            breakdown = res.get("cost_breakdown", {})
            move_s = breakdown.get("movement_s", 0)
            switch_s = breakdown.get("switch_channel_s", 0)
            detect_s = breakdown.get("detection_s", 0)

            print(f"📡 Measurement Complete: Position=({args.x}, {args.y}), Channel={args.channel}")
            if result_type == "direction":
                deg = res.get("svd_deg", 0.0)
                print(f"   - Result: Signal Detected (direction)")
                print(f"   - Bearing: {deg:.2f}° (Error Range: [-1°, 1°])")
            elif result_type == "near":
                print("   - Result: Signal Overload (near <= 5m, ready for direct clear)")
            else:
                print("   - Result: No Signal (out of range or outside directional coverage)")

            print(f"   - Virtual Clock: {v_time:.2f}s (+{dt:.2f}s | move:{move_s:.2f}s switch:{switch_s:.2f}s detect:{detect_s:.2f}s)")
        else:
            print(f"❌ Measure Rejected: {res}")
            sys.exit(1)


def handle_clear(args):
    client = get_client(args)
    res = client.clear(x=args.x, y=args.y, channel=args.channel)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("accepted"):
            clear_res = res.get("clear_result")
            v_time = res.get("virtual_time_s", 0)
            dt = res.get("consumed_virtual_duration_s", 0)
            breakdown = res.get("cost_breakdown", {})
            move_s = breakdown.get("movement_s", 0)
            detect_s = breakdown.get("detection_s", 0)
            clear_s = breakdown.get("clear_s", 0)

            print(f"🎯 Clear Operation: Position=({args.x}, {args.y}), Channel={args.channel}")
            if clear_res == "success":
                print("   - Result: 💥 Target Successfully Cleared! (Located within 20m and neutralized)")
            else:
                print("   - Result: ⚠️ Target Not Found (no target within 20m radius)")

            print(f"   - Virtual Clock: {v_time:.2f}s (+{dt:.2f}s | move:{move_s:.2f}s detect:{detect_s:.2f}s laser:{clear_s:.2f}s)")
        else:
            print(f"❌ Clear Rejected: {res}")
            sys.exit(1)


def handle_exit(args):
    client = get_client(args)
    res = client.exit()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("accepted"):
            print("🏁 Mission Finished (Session Exited)")
            print(f"   - Exit Reason: {res.get('exit_reason')}")
            print(f"   - Final Virtual Time: {res.get('virtual_time_s', 0):.2f}s")
        else:
            print(f"❌ Exit Failed: {res}")
            sys.exit(1)


def handle_status(args):
    client = get_client(args)
    res = client.ping()
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("online"):
            print(f"🟢 Simulator Online: {res.get('message')}")
        else:
            print(f"🔴 Simulator Offline: {res.get('message')}")
            if "error" in res:
                print(f"   Detail: {res['error']}")
            sys.exit(1)


def make_common_parser(is_sub=False):
    common = argparse.ArgumentParser(add_help=False)
    if is_sub:
        common.add_argument("--robot-id", default=argparse.SUPPRESS, help="Robot ID")
        common.add_argument("--base-url", default=argparse.SUPPRESS, help="Simulator URL")
        common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON")
    else:
        common.add_argument("--robot-id", default=DEFAULT_ROBOT_ID, help=f"Robot ID (default: {DEFAULT_ROBOT_ID})")
        common.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Simulator URL (default: {DEFAULT_BASE_URL})")
        common.add_argument("--json", action="store_true", default=False, help="Output JSON")
    return common


def main():
    root_common = make_common_parser(is_sub=False)
    sub_common = make_common_parser(is_sub=True)

    parser = argparse.ArgumentParser(
        parents=[root_common],
        description="Jammers Simulator Radio Localization & Neutralization CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    subparsers.add_parser("status", parents=[sub_common], help="Check if simulator endpoint is online and reachable")
    subparsers.add_parser("enter", parents=[sub_common], help="Enter target arena and start timer")

    p_measure = subparsers.add_parser("measure", parents=[sub_common], help="Move to (x, y) and measure bearing")
    p_measure.add_argument("x", type=float, help="Target X coordinate (meters)")
    p_measure.add_argument("y", type=float, help="Target Y coordinate (meters)")
    p_measure.add_argument("channel", type=int, choices=range(1, 21), help="Channel to detect (1~20)")

    p_clear = subparsers.add_parser("clear", parents=[sub_common], help="Move to (x, y) and clear target")
    p_clear.add_argument("x", type=float, help="Target X coordinate (meters)")
    p_clear.add_argument("y", type=float, help="Target Y coordinate (meters)")
    p_clear.add_argument("channel", type=int, choices=range(1, 21), help="Target channel to clear (1~20)")

    subparsers.add_parser("exit", parents=[sub_common], help="Exit mission and finalize run")

    args = parser.parse_args()

    commands = {
        "status": handle_status,
        "enter": handle_enter,
        "measure": handle_measure,
        "clear": handle_clear,
        "exit": handle_exit,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

