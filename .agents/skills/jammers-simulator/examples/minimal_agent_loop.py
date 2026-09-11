#!/usr/bin/env python3
"""
Minimal Autonomous Agent Exploration & Neutralization Loop
Demonstrates how an agent interacts with JammersSimulator-Tool programmatically.
"""

import os
import sys

# Add parent directory to path to import simulator_client
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from simulator_client import SimulatorClient


def run_minimal_agent():
    base_url = os.getenv("SIMULATOR_URL", "http://127.0.0.1:2026")
    client = SimulatorClient(base_url=base_url)

    print(f"[*] Step 0: Checking Simulator Health at {base_url}...")
    status = client.ping()
    if not status.get("online"):
        print(f"[-] Simulator is offline: {status.get('message')}")
        print("    Tip: Start mock_simulator.py or verify your connection/tunnel.")
        return

    print("[+] Simulator is ONLINE.")

    print("\n[*] Step 1: Entering Arena (/enter)...")
    enter_res = client.enter()
    if not enter_res.get("accepted"):
        print(f"[-] Enter rejected: {enter_res}")
        return
    print(f"[+] Arena entered. Remaining real time: {enter_res.get('remaining_real_duration_s')}s")

    # Step 2: Sample bearing from initial position (0, 0) on channels 1~5
    print("\n[*] Step 2: Sampling bearings on channels 1 to 5 at origin (0, 0)...")
    detected_channels = []
    for ch in range(1, 6):
        res = client.measure(x=0.0, y=0.0, channel=ch)
        res_type = res.get("measure_result")
        v_time = res.get("virtual_time_s")
        if res_type == "direction":
            bearing = res.get("svd_deg")
            print(f"    - Channel {ch}: Signal detected! Bearing={bearing:.2f}° (vClock: {v_time:.1f}s)")
            detected_channels.append((ch, bearing))
        elif res_type == "near":
            print(f"    - Channel {ch}: Direct near signal (<=5m)! Ready for immediate clear.")
            detected_channels.append((ch, None))
        else:
            print(f"    - Channel {ch}: No signal.")

    # Step 3: Direct approach test (illustrative)
    if detected_channels:
        target_ch, _ = detected_channels[0]
        print(f"\n[*] Step 3: Attempting precision search & clear on channel {target_ch} at (0, 0)...")
        clear_res = client.clear(x=0.0, y=0.0, channel=target_ch)
        print(f"    - Result: {clear_res.get('clear_result')} (vClock: {clear_res.get('virtual_time_s')}s)")

    # Step 4: Finalize session
    print("\n[*] Step 4: Exiting arena session (/exit)...")
    exit_res = client.exit()
    print(f"[+] Session finalized. Total virtual time: {exit_res.get('virtual_time_s', 0):.2f}s")


if __name__ == "__main__":
    run_minimal_agent()
