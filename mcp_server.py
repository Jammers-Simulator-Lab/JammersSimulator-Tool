#!/usr/bin/env python3
"""
Jammers Simulator Radio Localization & Neutralization System
Model Context Protocol (MCP) Server

Exposes core atomic actions (enter, measure, clear, exit) as standard MCP tools
enabling LLMs and autonomous agents to perform closed-loop exploration and control.
"""

import json
import os
import sys

# Ensure local simulator_client can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from mcp.server.mcpserver import MCPServer
from simulator_client import SimulatorClient

app = MCPServer(
    name="jammers-simulator-mcp",
    version="1.0.0",
    description="Jammers Simulator Official Interface MCP Tools",
)

client = SimulatorClient()


@app.tool(
    name="jammers_status",
    description=(
        "Check connection status and responsiveness of the arena simulator endpoint before entering a session."
    ),
)
def jammers_status() -> str:
    """Check connectivity to the simulator"""
    res = client.ping()
    return json.dumps(res, ensure_ascii=False, indent=2)


@app.tool(
    name="jammers_enter",
    description=(
        "Initialize jammers mission session, enter the target arena, and start the virtual clock."
        "Must be called once at the start of each mission run."
    ),
)
def jammers_enter(robot_id: str = "") -> str:
    """Enter arena and start mission"""
    if robot_id:
        client.robot_id = robot_id
    res = client.enter()
    return json.dumps(res, ensure_ascii=False, indent=2)


@app.tool(
    name="jammers_measure",
    description=(
        "Move to planar coordinate (x, y) and perform bearing measurement on specified channel (1~20).\n"
        "Return fields:\n"
        "- measure_result: 'direction' (signal detected) | 'near' (distance <= 5m overload blind zone) | 'no_signal' (out of range/blind zone)\n"
        "- svd_deg: bearing angle in degrees [0, 360), counterclockwise from East (0°), measurement error in [-1°, 1°]\n"
        "- consumed_virtual_duration_s: virtual time increment (distance/5m/s + channel_switch_1s + detect_5s)"
    ),
)
def jammers_measure(x: float, y: float, channel: int) -> str:
    """Move and perform bearing measurement"""
    if channel < 1 or channel > 20:
        return json.dumps({"error": f"Channel must be between 1 and 20, got {channel}"}, ensure_ascii=False)
    res = client.measure(x=x, y=y, channel=channel)
    return json.dumps(res, ensure_ascii=False, indent=2)


@app.tool(
    name="jammers_clear",
    description=(
        "Move to planar coordinate (x, y) and attempt precision optical detection and laser neutralization on target channel (1~20).\n"
        "Rules:\n"
        "- If distance <= 20m from target, laser automatically eliminates the jammer (takes 5s);\n"
        "- clear_result: 'success' (neutralized) | 'no_target_in_range' (no target within 20m, takes 3s);\n"
        "- Clear command does not switch the direction-finding channel (no switch cost)."
    ),
)
def jammers_clear(x: float, y: float, channel: int) -> str:
    """Move and attempt precision optical detection and laser neutralization"""
    if channel < 1 or channel > 20:
        return json.dumps({"error": f"Channel must be between 1 and 20, got {channel}"}, ensure_ascii=False)
    res = client.clear(x=x, y=y, channel=channel)
    return json.dumps(res, ensure_ascii=False, indent=2)


@app.tool(
    name="jammers_exit",
    description=(
        "End current mission session and exit the target arena."
        "Call when mission is completed or terminating."
    ),
)
def jammers_exit() -> str:
    """Exit mission session"""
    res = client.exit()
    return json.dumps(res, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    app.run(transport="stdio")
