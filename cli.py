#!/usr/bin/env python3
"""
Jammers Simulator Radio Localization & Neutralization CLI Toolchain
Supports both Problem 3 and Problem 4 with local in-memory simulation and live server modes.
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

from simulator_client import SimulatorClient, LocalSimulatorClient
from mock_simulator import run_mock_server

DEFAULT_ROBOT_ID = os.getenv("ROBOT_ID", "202622006078")
DEFAULT_BASE_URL = os.getenv("SIMULATOR_URL", "http://127.0.0.1:2026")


def get_client(args) -> SimulatorClient:
    return SimulatorClient(
        base_url=getattr(args, "base_url", DEFAULT_BASE_URL),
        robot_id=getattr(args, "robot_id", DEFAULT_ROBOT_ID),
        mode=getattr(args, "mode", "local"),
        problem=getattr(args, "problem", "q3"),
        seed=getattr(args, "seed", 42),
    )


def handle_status(args):
    client = get_client(args)
    res = client.ping()
    if getattr(args, "json", False):
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("online"):
            print(f"🟢 Simulator Online ({res.get('mode', 'live')}): {res.get('message', 'Ready')}")
        else:
            print(f"🔴 Simulator Offline: {res.get('message')}")
            if "error" in res:
                print(f"   Detail: {res['error']}")
            sys.exit(1)


def handle_enter(args):
    client = get_client(args)
    res = client.enter()
    if getattr(args, "json", False):
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
    if getattr(args, "json", False):
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
                print("   - Result: No Signal (out of range or outside directional coverage beam)")

            print(f"   - Virtual Clock: {v_time:.2f}s (+{dt:.2f}s | move:{move_s:.2f}s switch:{switch_s:.2f}s detect:{detect_s:.2f}s)")
        else:
            print(f"❌ Measure Rejected: {res}")
            sys.exit(1)


def handle_clear(args):
    client = get_client(args)
    res = client.clear(x=args.x, y=args.y, channel=args.channel)
    if getattr(args, "json", False):
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
    if getattr(args, "json", False):
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if res.get("accepted"):
            print("🏁 Mission Finished (Session Exited)")
            print(f"   - Exit Reason: {res.get('exit_reason')}")
            print(f"   - Final Virtual Time: {res.get('virtual_time_s', 0):.2f}s")
            summary = res.get("summary")
            if summary:
                print(f"   - Cleared: {summary.get('num_cleared')}/{summary.get('num_targets')} ({summary.get('cleared_ratio', 0)*100:.1f}%)")
        else:
            print(f"❌ Exit Failed: {res}")
            sys.exit(1)


def handle_ground_truth(args):
    client = get_client(args)
    res = client.get_ground_truth()
    if getattr(args, "json", False):
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("=" * 70)
        print(f"🎯 Arena Ground Truth (Problem: {res.get('problem', 'q3').upper()}, Seed: {res.get('seed')})")
        print(f"   Total Targets: {res.get('num_targets', 0)} (Omni: {res.get('num_omni', 0)}, Directional: {res.get('num_directional', 0)})")
        print("-" * 70)
        print(f"{'CH':^4} | {'Type':^12} | {'Coord (m)':^18} | {'Recv R (m)':^10} | {'Pointing':^10} | {'Status':^8}")
        print("-" * 70)
        for t in res.get("targets", []):
            pt_str = f"{t['pointing_deg']}°" if t.get("pointing_deg") is not None else "N/A (360°)"
            st_str = "CLEARED" if t.get("cleared") else "ACTIVE"
            pos_str = f"({t['x']:.1f}, {t['y']:.1f})"
            print(f"{t['channel']:^4} | {t['type']:^12} | {pos_str:^18} | {t['recv_radius']:^10.1f} | {pt_str:^10} | {st_str:^8}")
        print("=" * 70)


def handle_server(args):
    run_mock_server(port=args.port, problem=args.problem, seed=args.seed)


def handle_evaluate(args):
    from oracle_analyzer import OracleAnalyzer

    analyzer = OracleAnalyzer()
    cleared_targets = {}
    if args.targets:
        pairs = args.targets.strip().split(";")
        for p in pairs:
            if not p.strip():
                continue
            ch_str, xy_str = p.split(":")
            ch = int(ch_str.strip())
            x_str, y_str = xy_str.split(",")
            cleared_targets[ch] = (float(x_str.strip()), float(y_str.strip()))

    report = analyzer.diagnose(
        cleared_targets=cleared_targets if cleared_targets else None,
        actual_total_time=args.time if args.time > 0 else None,
    )

    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(analyzer.format_report(report))


def make_common_parser(is_sub=False):
    common = argparse.ArgumentParser(add_help=False)
    if is_sub:
        common.add_argument("--robot-id", default=argparse.SUPPRESS, help="Robot ID")
        common.add_argument("--base-url", default=argparse.SUPPRESS, help="Simulator URL")
        common.add_argument("--mode", choices=["local", "live", "auto"], default=argparse.SUPPRESS, help="Run mode")
        common.add_argument("--problem", choices=["q3", "q4"], default=argparse.SUPPRESS, help="Problem mode")
        common.add_argument("--seed", type=int, default=argparse.SUPPRESS, help="RNG seed")
        common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Output JSON")
    else:
        common.add_argument("--robot-id", default=DEFAULT_ROBOT_ID, help=f"Robot ID (default: {DEFAULT_ROBOT_ID})")
        common.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Simulator URL (default: {DEFAULT_BASE_URL})")
        common.add_argument("--mode", choices=["local", "live", "auto"], default="local", help="Mode: local (in-memory), live (HTTP), auto")
        common.add_argument("--problem", choices=["q3", "q4"], default="q3", help="Problem mode: q3 (omni) or q4 (hybrid)")
        common.add_argument("--seed", type=int, default=42, help="RNG seed for simulation (default: 42)")
        common.add_argument("--json", action="store_true", default=False, help="Output raw JSON")
    return common


def main():
    root_common = make_common_parser(is_sub=False)
    sub_common = make_common_parser(is_sub=True)

    parser = argparse.ArgumentParser(
        parents=[root_common],
        description="Jammers Simulator Radio Localization & Neutralization Unified CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    subparsers.add_parser("status", parents=[sub_common], help="Check if simulator endpoint is online")
    subparsers.add_parser("enter", parents=[sub_common], help="Enter arena and start timer")

    p_measure = subparsers.add_parser("measure", parents=[sub_common], help="Move to (x, y) and measure bearing")
    p_measure.add_argument("x", type=float, help="Target X coordinate (meters)")
    p_measure.add_argument("y", type=float, help="Target Y coordinate (meters)")
    p_measure.add_argument("channel", type=int, choices=range(1, 21), help="Channel to detect (1~20)")

    p_clear = subparsers.add_parser("clear", parents=[sub_common], help="Move to (x, y) and clear target")
    p_clear.add_argument("x", type=float, help="Target X coordinate (meters)")
    p_clear.add_argument("y", type=float, help="Target Y coordinate (meters)")
    p_clear.add_argument("channel", type=int, choices=range(1, 21), help="Target channel to clear (1~20)")

    subparsers.add_parser("exit", parents=[sub_common], help="Exit mission and finalize run")
    subparsers.add_parser("ground_truth", parents=[sub_common], help="Query arena target locations and radiation parameters")

    p_server = subparsers.add_parser("server", parents=[sub_common], help="Launch local standalone HTTP mock server")
    p_server.add_argument("--port", "-p", type=int, default=2026, help="Listening port (default: 2026)")

    p_eval = subparsers.add_parser("evaluate", parents=[sub_common], help="Compute Oracle theoretical bound")
    p_eval.add_argument("--targets", type=str, default="", help="Target list: '11:281.5,141.0;1:455.2,357.9'")
    p_eval.add_argument("--time", type=float, default=0.0, help="Actual mission virtual time in seconds")

    args = parser.parse_args()

    commands = {
        "status": handle_status,
        "enter": handle_enter,
        "measure": handle_measure,
        "clear": handle_clear,
        "exit": handle_exit,
        "ground_truth": handle_ground_truth,
        "server": handle_server,
        "evaluate": handle_evaluate,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
