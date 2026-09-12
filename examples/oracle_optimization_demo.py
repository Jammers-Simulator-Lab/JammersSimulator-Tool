#!/usr/bin/env python3
"""
Example: Real-time Mission with Pluggable Oracle Theoretical Bound & Optimization Diagnostic
Demonstrates how to enable automatic Oracle performance benchmarking and gap attribution.
"""

import os
import sys

# Ensure local simulator_client can be imported
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from simulator_client import SimulatorClient

def run_oracle_demo():
    base_url = os.getenv("SIMULATOR_URL", "http://127.0.0.1:2026")
    
    # Initialize client with optional analyzer enabled!
    client = SimulatorClient(base_url=base_url, enable_analyzer=True)

    print("=" * 70)
    print("🚀 Running Session with Pluggable Oracle Analyzer Enabled...")
    print("=" * 70)

    # In a typical mission, client methods are called:
    # client.enter()
    # client.measure(...)
    # client.clear(...)
    # client.exit()

    # Demonstrating evaluation report:
    print("\n[*] Fetching Real-Time Oracle Bound Report from Client Analyzer:")
    # We can also supply known cleared targets directly to the analyzer for offline evaluation:
    demo_cleared = {
        11: (281.5, 141.0),
        1:  (455.2, 357.9),
        4:  (78.5, 573.9),
        20: (187.8, 704.9),
        13: (588.1, 1140.9),
    }
    report = client.analyzer.diagnose(cleared_targets=demo_cleared, actual_total_time=791.34)
    print(client.analyzer.format_report(report))

if __name__ == "__main__":
    run_oracle_demo()
