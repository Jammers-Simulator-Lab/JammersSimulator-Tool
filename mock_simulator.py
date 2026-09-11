#!/usr/bin/env python3
"""
Jammers Simulator Radio Localization & Neutralization Toolchain
Local Testing Mock Server for Driver Debugging and Unit Tests

Provides an in-memory HTTP service matching the official contest simulator endpoints
(/enter, /measure, /clear, /exit) for offline development, CI verification, and agent testing
when the official Windows simulation GUI is not running.
"""

import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional


class MockArena:
    def __init__(self, seed: Optional[int] = 42):
        self.rng = random.Random(seed)
        self.arena_radius = 1800.0
        self.speed = 5.0  # 5 m/s
        self.active_session = False

        # Initial state
        self.current_pos = {"x": 0.0, "y": 0.0}
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.start_real_time_ms = 0

        # Generate 10~16 targets distributed in arena
        self.num_targets = self.rng.randint(10, 16)
        all_channels = list(range(1, 21))
        self.rng.shuffle(all_channels)
        self.target_channels = sorted(all_channels[: self.num_targets])

        self.targets: Dict[int, Dict] = {}
        for ch in self.target_channels:
            r = self.arena_radius * math.sqrt(self.rng.random())
            theta = self.rng.uniform(0, 2 * math.pi)
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            recv_radius = self.rng.uniform(1000.0, 1500.0)
            self.targets[ch] = {
                "channel": ch,
                "x": x,
                "y": y,
                "recv_radius": recv_radius,
                "cleared": False,
            }

    def reset_session(self):
        self.active_session = True
        self.current_pos = {"x": 0.0, "y": 0.0}
        self.current_channel = 1
        self.virtual_time_s = 0.0
        self.start_real_time_ms = int(time.time() * 1000)

    def handle_enter(self, robot_id: str) -> Dict:
        self.reset_session()
        return {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": 0,
            "max_virtual_duration_s": 360000,
            "max_real_duration_s": 1200,
            "remaining_real_duration_s": 1200,
        }

    def handle_measure(self, x: float, y: float, channel: int) -> Dict:
        if not self.active_session:
            return {"accepted": False, "error": "session_not_active"}

        dx = x - self.current_pos["x"]
        dy = y - self.current_pos["y"]
        dist = math.hypot(dx, dy)
        move_s = dist / self.speed

        switch_s = 1.0 if channel != self.current_channel else 0.0
        detect_s = 5.0
        total_dt = move_s + switch_s + detect_s

        self.current_pos = {"x": x, "y": y}
        self.current_channel = channel
        self.virtual_time_s += total_dt

        target = self.targets.get(channel)
        if not target or target["cleared"]:
            res_type = "no_signal"
            svd_deg = None
        else:
            t_dist = math.hypot(target["x"] - x, target["y"] - y)
            if t_dist > target["recv_radius"]:
                res_type = "no_signal"
                svd_deg = None
            elif t_dist <= 5.0:
                res_type = "near"
                svd_deg = None
            else:
                res_type = "direction"
                true_deg = math.degrees(math.atan2(target["y"] - y, target["x"] - x)) % 360.0
                err = self.rng.uniform(-1.0, 1.0)
                svd_deg = round((true_deg + err) % 360.0, 2)

        resp = {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual_time_s, 2),
            "position": {"x": x, "y": y},
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

    def handle_clear(self, x: float, y: float, channel: int) -> Dict:
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
            if t_dist <= 20.0:
                is_success = True
                target["cleared"] = True

        clear_s = 2.0 if is_success else 0.0
        total_dt = move_s + detect_s + clear_s

        self.current_pos = {"x": x, "y": y}
        self.virtual_time_s += total_dt

        return {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual_time_s, 2),
            "position": {"x": x, "y": y},
            "channel": channel,
            "consumed_virtual_duration_s": round(total_dt, 2),
            "cost_breakdown": {
                "movement_s": round(move_s, 2),
                "detection_s": round(detect_s, 2),
                "clear_s": round(clear_s, 2),
            },
            "clear_result": "success" if is_success else "no_target_in_range",
        }

    def handle_exit(self) -> Dict:
        self.active_session = False
        return {
            "accepted": True,
            "real_timestamp_ms": int(time.time() * 1000),
            "virtual_time_s": round(self.virtual_time_s, 2),
            "exit_reason": "user_exit",
        }


arena = MockArena()


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Quiet console

    def do_GET(self):
        if self.path in ["/ping", "/status", "/"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"online": True, "service": "JammersSimulatorMock"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        data = json.loads(body.decode("utf-8")) if body else {}

        if self.path == "/enter":
            res = arena.handle_enter(data.get("robot_id", ""))
        elif self.path == "/measure":
            pos = data.get("position", {"x": 0, "y": 0})
            res = arena.handle_measure(pos.get("x", 0), pos.get("y", 0), data.get("channel", 1))
        elif self.path == "/clear":
            pos = data.get("position", {"x": 0, "y": 0})
            res = arena.handle_clear(pos.get("x", 0), pos.get("y", 0), data.get("channel", 1))
        elif self.path == "/exit":
            res = arena.handle_exit()
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(res).encode("utf-8"))


def run_mock_server(port: int = 2027):
    server = HTTPServer(("127.0.0.1", port), MockHandler)
    print(f"Mock Simulator listening on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    import sys
    p = int(sys.argv[1]) if len(sys.argv) > 1 else 2027
    run_mock_server(p)
