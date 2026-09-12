"""
Jammers Simulator Radio Localization & Neutralization System
HTTP REST API Client Driver
"""

import json
import os
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from http.client import RemoteDisconnected


class SimulatorClient:
    def __init__(
        self,
        base_url: str = os.getenv("SIMULATOR_URL", "http://127.0.0.1:2026"),
        robot_id: str = os.getenv("ROBOT_ID", "<YOUR_ROBOT_ID>"),
        arena_id: str = "default",
        enable_analyzer: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.robot_id = robot_id
        self.arena_id = arena_id
        self.request_counter = 0
        self.enable_analyzer = enable_analyzer
        self.analyzer = None
        if enable_analyzer:
            try:
                from oracle_analyzer import OracleAnalyzer
                self.analyzer = OracleAnalyzer()
            except ImportError:
                pass

    def _gen_req_id(self, prefix: str) -> str:
        self.request_counter += 1
        return f"{prefix}-{self.request_counter}-{int(time.time() * 1000)}"

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
                "message": f"Failed to connect to simulator at {url}. Please ensure simulator server is active and interface is ready.",
                "detail": str(e),
            }

    def enter(self) -> Dict[str, Any]:
        """Enter target arena and start mission clock"""
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
        payload = {
            "arena_id": self.arena_id,
            "robot_id": self.robot_id,
            "request_id": self._gen_req_id("exit"),
        }
        res = self._post("/exit", payload)
        if self.analyzer and res.get("accepted"):
            self.analyzer.record_exit(res)
        return res

    def get_oracle_report(self) -> Dict[str, Any]:
        """Get the Oracle theoretical lower bound and gap attribution diagnosis"""
        if not self.analyzer:
            return {
                "error": "Analyzer is not enabled. Initialize SimulatorClient with enable_analyzer=True."
            }
        return self.analyzer.diagnose()

    def print_oracle_report(self):
        """Print human-readable diagnostic report to console"""
        if not self.analyzer:
            print("[-] Analyzer is not enabled. Initialize SimulatorClient with enable_analyzer=True.")
            return
        print(self.analyzer.format_report())

    def ping(self, timeout: float = 2.0) -> Dict[str, Any]:
        """Check if the simulator server port is listening and responsive"""
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
            return {
                "online": True,
                "base_url": self.base_url,
                "message": f"Simulator server is online and listening on {host}:{port}.",
            }
        except Exception as e:
            return {
                "online": False,
                "base_url": self.base_url,
                "error": str(e),
                "message": f"Cannot connect to simulator on {host}:{port}. Ensure simulator or SSH tunnel is active.",
            }

