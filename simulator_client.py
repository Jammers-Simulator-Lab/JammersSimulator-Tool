"""
Jammers Simulator Radio Localization & Neutralization System
Unified HTTP REST API & High-Fidelity Local Client Driver

Supports:
- Both Question 3 (Q3: omnidirectional) and Question 4 (Q4: hybrid omni/directional)
- Dual-mode execution:
    * "local": High-fidelity in-memory simulation (0.15s / run, zero network latency)
    * "live": Official Windows simulator connection via HTTP REST API
    * "auto": Automatic probing with graceful local failover if live service is unavailable
"""

import json
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from http.client import RemoteDisconnected


class LocalSimulatorClient:
    """
    High-fidelity in-memory mock client implementing the identical protocol
    interface as the official simulator. Runs 1000x faster for Monte Carlo benchmarks,
    strategy training, and rapid local iteration.
    """

    def __init__(
        self,
        problem: str = "q3",
        seed: Optional[int] = 42,
        enable_analyzer: bool = False,
    ):
        from mock_simulator import MockArena

        self.problem = problem.lower().strip()
        self.seed = seed
        self.arena = MockArena(problem=self.problem, seed=self.seed)
        self.targets: Dict[int, Tuple[float, float]] = {
            ch: (t["x"], t["y"]) for ch, t in self.arena.targets.items()
        }
        self.robot_id = "local_robot"
        self.enable_analyzer = enable_analyzer
        self.analyzer = None
        if enable_analyzer:
            try:
                from oracle_analyzer import OracleAnalyzer

                self.analyzer = OracleAnalyzer()
            except ImportError:
                pass

    @property
    def virtual_time_s(self) -> float:
        return self.arena.virtual_time_s

    @property
    def current_pos(self) -> Dict[str, float]:
        return self.arena.current_pos

    @property
    def current_channel(self) -> int:
        return self.arena.current_channel

    def enter(self) -> Dict[str, Any]:
        res = self.arena.handle_enter(robot_id=self.robot_id)
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_enter(res)
        return res

    def measure(self, x: float, y: float, channel: int) -> Dict[str, Any]:
        res = self.arena.handle_measure(float(x), float(y), int(channel))
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_measure(x, y, channel, res)
        return res

    def clear(self, x: float, y: float, channel: int) -> Dict[str, Any]:
        res = self.arena.handle_clear(float(x), float(y), int(channel))
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_clear(x, y, channel, res)
        return res

    def exit(self) -> Dict[str, Any]:
        res = self.arena.handle_exit()
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_exit(res)
        return res

    def get_ground_truth(self) -> Dict[str, Any]:
        return self.arena.get_ground_truth()

    def ping(self, timeout: float = 1.0) -> Dict[str, Any]:
        return {
            "online": True,
            "mode": "local",
            "problem": self.problem,
            "seed": self.seed,
            "targets_count": self.arena.num_targets,
            "message": f"Local simulator active (Problem: {self.problem.upper()}, Seed: {self.seed}).",
        }

    def get_oracle_report(self) -> Dict[str, Any]:
        if not self.analyzer:
            return {
                "error": "Analyzer is not enabled. Initialize with enable_analyzer=True."
            }
        return self.analyzer.diagnose()


class SimulatorClient:
    """
    Unified client supporting:
    - mode="local": In-memory simulation using LocalSimulatorClient
    - mode="live": HTTP client communicating with official Windows contest simulator
    - mode="auto": Probes official simulator; automatically switches to local on connection failure
    """

    def __init__(
        self,
        base_url: str = os.getenv("SIMULATOR_URL", "http://127.0.0.1:2026"),
        robot_id: str = os.getenv("ROBOT_ID", "<YOUR_ROBOT_ID>"),
        arena_id: str = "default",
        mode: str = "local",  # default to local for robust offline simulation
        problem: str = "q3",
        seed: Optional[int] = 42,
        enable_analyzer: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id
        self.arena_id = arena_id
        self.mode = mode.lower().strip()
        self.problem = problem.lower().strip()
        self.seed = seed
        self.request_counter = 0
        self.enable_analyzer = enable_analyzer

        self._local_backend: Optional[LocalSimulatorClient] = None
        self._is_live = False

        self.analyzer = None
        if enable_analyzer:
            try:
                from oracle_analyzer import OracleAnalyzer

                self.analyzer = OracleAnalyzer()
            except ImportError:
                pass

        if self.mode == "local":
            self._local_backend = LocalSimulatorClient(
                problem=self.problem, seed=self.seed, enable_analyzer=self.enable_analyzer
            )
            self._is_live = False
        elif self.mode == "auto":
            probe = self._probe_live()
            if probe.get("online"):
                self._is_live = True
            else:
                print(f"⚠️ [SimulatorClient] Official simulator at {self.base_url} is unreachable.")
                print(f"🏠 Automatically fell back to Local Simulator Backend (Problem: {self.problem.upper()}, Seed: {self.seed}).")
                self._local_backend = LocalSimulatorClient(
                    problem=self.problem, seed=self.seed, enable_analyzer=self.enable_analyzer
                )
                self._is_live = False
        else:  # 'live'
            self._is_live = True

    @property
    def is_local(self) -> bool:
        return not self._is_live

    @property
    def targets(self) -> Optional[Dict[int, Tuple[float, float]]]:
        if self._local_backend:
            return self._local_backend.targets
        return None

    def _gen_req_id(self, prefix: str) -> str:
        self.request_counter += 1
        return f"{prefix}-{self.request_counter}-{int(time.time() * 1000)}"

    def _probe_live(self, timeout: float = 1.0) -> Dict[str, Any]:
        """Check if remote HTTP port is listening"""
        import socket
        import urllib.parse

        parsed = urllib.parse.urlparse(self.base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 2026
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            s.close()
            return {"online": True, "base_url": self.base_url}
        except Exception as e:
            return {"online": False, "base_url": self.base_url, "error": str(e)}

    def ping(self, timeout: float = 1.5) -> Dict[str, Any]:
        if not self._is_live and self._local_backend:
            return self._local_backend.ping(timeout)
        return self._probe_live(timeout)

    def _post(self, path: str, payload: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        url = self.base_url + path
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            try:
                return json.loads(err_body)
            except Exception:
                return {"accepted": False, "error": f"HTTP {e.code}: {e.reason}", "raw": err_body}
        except (URLError, RemoteDisconnected, ConnectionResetError, ConnectionRefusedError) as e:
            return {
                "accepted": False,
                "error": "connection_failed",
                "message": f"Failed to connect to simulator at {url}. Ensure server is active.",
                "detail": str(e),
            }

    def enter(self) -> Dict[str, Any]:
        """Enter target arena and start mission clock"""
        if not self._is_live and self._local_backend:
            return self._local_backend.enter()

        payload = {
            "arena_id": self.arena_id,
            "robot_id": self.robot_id,
            "request_id": self._gen_req_id("enter"),
        }
        res = self._post("/enter", payload)
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_enter(res)
        return res

    def measure(self, x: float, y: float, channel: int) -> Dict[str, Any]:
        """
        Move to (x, y) and perform bearing measurement on specified channel.
        Returns:
        - measure_result: 'direction' | 'near' | 'no_signal'
        - svd_deg: bearing angle in degrees [0, 360) with [-1, 1] deg measurement noise
        - consumed_virtual_duration_s: time elapsed (move + switch + measure)
        """
        if not self._is_live and self._local_backend:
            return self._local_backend.measure(x, y, channel)

        payload = {
            "arena_id": self.arena_id,
            "robot_id": self.robot_id,
            "request_id": self._gen_req_id("measure"),
            "position": {"x": float(x), "y": float(y)},
            "channel": int(channel),
        }
        res = self._post("/measure", payload)
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_measure(x, y, channel, res)
        return res

    def clear(self, x: float, y: float, channel: int) -> Dict[str, Any]:
        """
        Move to (x, y) and attempt precision optical detection and laser neutralization.
        Effective within distance <= 20 meters.
        """
        if not self._is_live and self._local_backend:
            return self._local_backend.clear(x, y, channel)

        payload = {
            "arena_id": self.arena_id,
            "robot_id": self.robot_id,
            "request_id": self._gen_req_id("clear"),
            "position": {"x": float(x), "y": float(y)},
            "channel": int(channel),
        }
        res = self._post("/clear", payload)
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_clear(x, y, channel, res)
        return res

    def exit(self) -> Dict[str, Any]:
        """Terminate mission session and finalize log"""
        if not self._is_live and self._local_backend:
            return self._local_backend.exit()

        payload = {
            "arena_id": self.arena_id,
            "robot_id": self.robot_id,
            "request_id": self._gen_req_id("exit"),
        }
        res = self._post("/exit", payload)
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_exit(res)
        return res

    def get_ground_truth(self) -> Dict[str, Any]:
        """Query simulation ground truth (available in local mode or local mock server)"""
        if not self._is_live and self._local_backend:
            return self._local_backend.get_ground_truth()

        url = self.base_url + "/ground_truth"
        req = Request(url, headers={"Content-Type": "application/json"}, method="GET")
        try:
            with urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"accepted": False, "error": str(e), "message": "Ground truth endpoint not available on official live server."}

    def get_oracle_report(self) -> Dict[str, Any]:
        """Get Oracle theoretical bound analysis"""
        if not self._is_live and self._local_backend:
            return self._local_backend.get_oracle_report()
        if not self.analyzer:
            return {"error": "Analyzer is not enabled. Initialize SimulatorClient with enable_analyzer=True."}
        return self.analyzer.diagnose()
