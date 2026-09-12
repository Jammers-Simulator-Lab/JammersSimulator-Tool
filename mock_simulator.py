#!/usr/bin/env python3
"""
Jammers Simulator Radio Localization & Neutralization Toolchain
High-Fidelity Local Mock Simulator for Problem 3 and Problem 4

Provides an in-memory high-fidelity simulation engine matching the official
contest simulator endpoints (/enter, /measure, /clear, /exit, /ground_truth)
and supports both:
- Question 3 (Q3): Omnidirectional jammers (10~16 targets, 360° radiation)
- Question 4 (Q4): Hybrid omnidirectional and directional jammers (10~16 targets,
                   directional jammers emit within a 180° beam [-90°, +90°] centered
                   at unknown pointing angles).
"""

import argparse
import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Tuple


class MockArena:
    def __init__(self, problem: str = "q3", seed: Optional[int] = 42):
        self.problem = problem.lower().strip()
        self.seed = seed
        self.rng = random.Random(seed)
        self.arena_radius = 1800.0
        self.speed = 5.0  # 5.0 m/s
        self.active_session = False

        # Initial kinematics & clock state
        self.current_pos = {"x": 0.0, "y": 0.0}
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.start_real_time_ms = 0

        # Generate 10~16 targets distributed in arena
        self.num_targets = self.rng.randint(10, 16)
        all_channels = list(range(1, 21))
        self.rng.shuffle(all_channels)
        self.target_channels = sorted(all_channels[: self.num_targets])

        # Directional jammer allocation for Q4
        if self.problem in ["q4", "question4", "problem4", "p4"]:
            min_dir = max(1, int(round(self.num_targets * 0.3)))
            max_dir = min(self.num_targets - 1, max(1, int(round(self.num_targets * 0.7))))
            self.num_directional = self.rng.randint(min_dir, max_dir)
            self.num_omni = self.num_targets - self.num_directional
            shuffled_chs = list(self.target_channels)
            self.rng.shuffle(shuffled_chs)
            directional_chs = set(shuffled_chs[: self.num_directional])
        else:
            self.problem = "q3"
            self.num_directional = 0
            self.num_omni = self.num_targets
            directional_chs = set()

        self.targets: Dict[int, Dict[str, Any]] = {}
        for ch in self.target_channels:
            r = self.arena_radius * math.sqrt(self.rng.random())
            theta = self.rng.uniform(0, 2 * math.pi)
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            recv_radius = self.rng.uniform(1000.0, 1500.0)

            is_directional = ch in directional_chs
            pointing_deg = round(self.rng.uniform(0.0, 360.0), 2) if is_directional else None

            self.targets[ch] = {
                "channel": ch,
                "x": round(x, 2),
                "y": round(y, 2),
                "recv_radius": round(recv_radius, 2),
                "type": "directional" if is_directional else "omni",
                "pointing_deg": pointing_deg,
                "cleared": False,
            }

    def reset_session(self):
        """Reset session state to start position (0, 0) and channel 1"""
        self.active_session = True
        self.current_pos = {"x": 0.0, "y": 0.0}
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.start_real_time_ms = int(time.time() * 1000)

    def handle_enter(self, robot_id: str = "") -> Dict[str, Any]:
        """POST /enter implementation"""
        self.reset_session()
        return {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": 0.0,
            "max_virtual_duration_s": 360000,
            "max_real_duration_s": 1200,
            "remaining_real_duration_s": 1200,
        }

    def handle_measure(self, x: float, y: float, channel: int) -> Dict[str, Any]:
        """POST /measure implementation with Q3 omni and Q4 directional lobe handling"""
        if not self.active_session:
            return {"accepted": False, "error": "session_not_active"}

        dx = x - self.current_pos["x"]
        dy = y - self.current_pos["y"]
        dist = math.hypot(dx, dy)
        move_s = dist / self.speed

        switch_s = 1.0 if channel != self.current_channel else 0.0
        detect_s = 5.0
        total_dt = move_s + switch_s + detect_s

        self.current_pos = {"x": round(x, 2), "y": round(y, 2)}
        self.current_channel = channel
        self.virtual_time_s += total_dt

        target = self.targets.get(channel)
        if not target or target["cleared"]:
            res_type = "no_signal"
            svd_deg = None
        else:
            t_dist = math.hypot(target["x"] - x, target["y"] - y)
            if t_dist > target["recv_radius"]:
                # Exceeds maximum radio reception range
                res_type = "no_signal"
                svd_deg = None
            else:
                # Range is within recv_radius. Check directional beam if Q4 directional jammer
                in_beam = True
                if target["type"] == "directional":
                    # Angle from target to robot
                    dx_t = x - target["x"]
                    dy_t = y - target["y"]
                    dog_angle = math.degrees(math.atan2(dy_t, dx_t)) % 360.0
                    ang_diff = abs((dog_angle - target["pointing_deg"] + 180.0) % 360.0 - 180.0)
                    if ang_diff > 90.0:
                        # Dog is outside the +/- 90 degree main coverage sector
                        in_beam = False

                if not in_beam:
                    res_type = "no_signal"
                    svd_deg = None
                elif t_dist <= 5.0:
                    # Signal overload near-field blind zone
                    res_type = "near"
                    svd_deg = None
                else:
                    # Direction finding bearing angle with [-1.0, 1.0] deg error
                    res_type = "direction"
                    true_deg = math.degrees(math.atan2(target["y"] - y, target["x"] - x)) % 360.0
                    err = self.rng.uniform(-1.0, 1.0)
                    svd_deg = round((true_deg + err) % 360.0, 2)

        resp = {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual_time_s, 2),
            "position": {"x": round(x, 2), "y": round(y, 2)},
            "channel": channel,
            "consumed_virtual_duration_s": round(total_dt, 2),
            "cost_breakdown": {
                "movement_s": round(move_s, 2),
                "switch_channel_s": round(switch_s, 2),
                "detection_s": round(detect_s, 2),
            },
            "measure_result": res_type,
        }
        if svd_deg is not None:
            resp["svd_deg"] = svd_deg
        return resp

    def handle_clear(self, x: float, y: float, channel: int) -> Dict[str, Any]:
        """POST /clear implementation (optical acquisition + laser neutralization)"""
        if not self.active_session:
            return {"accepted": False, "error": "session_not_active"}

        dx = x - self.current_pos["x"]
        dy = y - self.current_pos["y"]
        dist = math.hypot(dx, dy)
        move_s = dist / self.speed
        detect_s = 3.0

        target = self.targets.get(channel)
        is_success = False
        if target and not target["cleared"]:
            t_dist = math.hypot(target["x"] - x, target["y"] - y)
            # Optical detection & clearance strictly within 20m radius (independent of RF beam)
            if t_dist <= 20.0:
                is_success = True
                target["cleared"] = True

        clear_s = 2.0 if is_success else 0.0
        total_dt = move_s + detect_s + clear_s

        self.current_pos = {"x": round(x, 2), "y": round(y, 2)}
        self.virtual_time_s += total_dt

        return {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual_time_s, 2),
            "position": {"x": round(x, 2), "y": round(y, 2)},
            "channel": channel,
            "consumed_virtual_duration_s": round(total_dt, 2),
            "cost_breakdown": {
                "movement_s": round(move_s, 2),
                "detection_s": round(detect_s, 2),
                "clear_s": round(clear_s, 2),
            },
            "clear_result": "success" if is_success else "no_target_in_range",
        }

    def handle_exit(self) -> Dict[str, Any]:
        """POST /exit implementation"""
        self.active_session = False
        cleared_count = sum(1 for t in self.targets.values() if t["cleared"])
        return {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual_time_s, 2),
            "exit_reason": "user_exit",
            "summary": {
                "problem": self.problem,
                "seed": self.seed,
                "num_targets": self.num_targets,
                "num_omni": self.num_omni,
                "num_directional": self.num_directional,
                "num_cleared": cleared_count,
                "cleared_ratio": round(cleared_count / max(self.num_targets, 1), 4),
                "avg_time_s": round(self.virtual_time_s / max(cleared_count, 1), 2),
            },
        }

    def get_ground_truth(self) -> Dict[str, Any]:
        """Retrieve target positions, types, radiation angles, and status for verification"""
        return {
            "problem": self.problem,
            "seed": self.seed,
            "arena_radius": self.arena_radius,
            "num_targets": self.num_targets,
            "num_omni": self.num_omni,
            "num_directional": self.num_directional,
            "targets": [
                {
                    "channel": t["channel"],
                    "x": t["x"],
                    "y": t["y"],
                    "recv_radius": t["recv_radius"],
                    "type": t["type"],
                    "pointing_deg": t["pointing_deg"],
                    "cleared": t["cleared"],
                }
                for t in self.targets.values()
            ],
        }


# Global arena instance for HTTP handler
global_arena = MockArena(problem="q3", seed=42)


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet logging

    def do_GET(self):
        if self.path in ["/ping", "/status", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "online": True,
                        "service": "JammersSimulatorMock",
                        "problem": global_arena.problem,
                        "seed": global_arena.seed,
                    }
                ).encode("utf-8")
            )
        elif self.path == "/ground_truth":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(global_arena.get_ground_truth()).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global global_arena
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        data = json.loads(body.decode("utf-8")) if body else {}

        if self.path == "/enter":
            res = global_arena.handle_enter(data.get("robot_id", ""))
        elif self.path == "/measure":
            pos = data.get("position", {"x": 0, "y": 0})
            res = global_arena.handle_measure(pos.get("x", 0), pos.get("y", 0), data.get("channel", 1))
        elif self.path == "/clear":
            pos = data.get("position", {"x": 0, "y": 0})
            res = global_arena.handle_clear(pos.get("x", 0), pos.get("y", 0), data.get("channel", 1))
        elif self.path == "/exit":
            res = global_arena.handle_exit()
        elif self.path == "/config":
            # Dynamically reconfigure arena problem / seed
            prob = data.get("problem", global_arena.problem)
            seed = data.get("seed", global_arena.seed)
            global_arena = MockArena(problem=prob, seed=seed)
            res = {"accepted": True, "problem": global_arena.problem, "seed": global_arena.seed}
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(res).encode("utf-8"))


def run_mock_server(port: int = 2026, problem: str = "q3", seed: Optional[int] = 42):
    global global_arena
    global_arena = MockArena(problem=problem, seed=seed)
    server = HTTPServer(("127.0.0.1", port), MockHandler)
    print("=" * 70)
    print(f"📡 [JammersSimulator Mock Server] Listening on http://127.0.0.1:{port}")
    print(f"   Mode: {problem.upper()} ({'Hybrid Omni/Directional' if 'q4' in problem.lower() else 'Pure Omnidirectional'})")
    print(f"   Seed: {seed} | Total Targets: {global_arena.num_targets}")
    if global_arena.num_directional > 0:
        print(f"   Breakdown: {global_arena.num_omni} Omni + {global_arena.num_directional} Directional")
    print("=" * 70)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Mock Simulator Server...")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jammers Simulator Local Mock Server")
    parser.add_argument("--port", "-p", type=int, default=2026, help="Listening port (default: 2026)")
    parser.add_argument("--problem", choices=["q3", "q4"], default="q3", help="Contest problem (q3 or q4)")
    parser.add_argument("--seed", "-s", type=int, default=42, help="RNG seed for reproducible target generation")
    args = parser.parse_args()

    run_mock_server(port=args.port, problem=args.problem, seed=args.seed)
