---
name: jammers-simulator
description: |
  Autonomous toolchain for CUMCM 2026 Problem B (Radio Jammer Localization & Neutralization).
  Provides dual-surface control via native CLI (`cli.py`) and Model Context Protocol (MCP) server (`mcp_server.py`).
  Use when the agent needs to check simulator health, enter the arena, measure radio bearing angles, navigate, triangulate emitter coordinates, trigger optical-laser neutralization, or exit test sessions.
  Triggers: "/jammers-simulator", "jammers-simulator", "jammers simulator", "jammers cli", "jammers mcp", "cumcm problem b", "jammers measure", "jammers clear", "jammer localization", "bearing measurement", "laser neutralization".
user-invocable: true
---

# Jammers Simulator Agent Skill

This skill equips the autonomous agent with deterministic operational workflows and decision logic to orchestrate autonomous navigation, radio direction-finding (RDF), and precision optical-laser neutralization.

---

## 1. Dual-Surface Execution Modes

The agent can invoke operations through either **CLI mode** or **MCP mode**:

| Surface | Invocation Mechanism | Recommended Use Case |
| :--- | :--- | :--- |
| **Native CLI** | `python3 cli.py <cmd> --json` | Scripting, automated batch tests, pipeline integration, shell environments |
| **MCP Tools** | `jammers_status`, `jammers_enter`, `jammers_measure`, `jammers_clear`, `jammers_exit` | Interactive LLM chat loops (Claude Desktop, Antigravity, Cursor) |

> **Rule for Agents**: Always specify `--json` when invoking `cli.py` so outputs are returned as structured, parseable JSON payloads.

---

## 2. Deterministic Agent Execution Loop

Follow this 6-stage phased decision cycle:

```
[Phase 1: Health Check] ──> [Phase 2: Enter Arena] ──> [Phase 3: Coarse Survey]
                                                               │
[Phase 6: Session Exit] <── [Phase 5: Laser Neutralize] <── [Phase 4: Triangulate]
```

### Phase 1: Pre-Flight Health Check
Always verify the simulator endpoint is listening before starting a run.
- **CLI**: `python3 cli.py status --json`
- **MCP**: `jammers_status()`
- **Failure Recovery**: If `online: false`, check whether `mock_simulator.py` or the SSH tunnel to the arena server is active.

### Phase 2: Session Initialization
Enters the arena, sets coordinate to $(0, 0)$, and starts the virtual timer. Must be called exactly once.
- **CLI**: `python3 cli.py enter --json`
- **MCP**: `jammers_enter()`
- **Check**: Verify `accepted: true`.

### Phase 3: Coarse RDF Bearing Survey (Minimize Channel Switching!)
- **Cost Rule**: Switching channels costs $1.0\,\text{s}$; measuring without switching costs $0\,\text{s}$ switch penalty.
- **Strategy**: When surveying multiple channels at a single observation point $(x_0, y_0)$, batch scan channels $c \in [1, 20]$ in succession without moving.
- **CLI**: `python3 cli.py measure <x> <y> <channel> --json`
- **MCP**: `jammers_measure(x, y, channel)`

### Phase 4: Trajectory & Bearing Triangulation
- When a channel returns `measure_result = "direction"` with angle $\theta_1$ at $(x_1, y_1)$, move to a baseline position $(x_2, y_2)$ perpendicular to the line of bearing to measure $\theta_2$.
- Compute the intersecting planar coordinate $(\hat{x}, \hat{y})$:
  $$y - y_i = \tan(\theta_i)(x - x_i), \quad i \in \{1, 2\}$$
- Account for $\pm 1^\circ$ noise by treating intersection as an uncertainty ellipse.

### Phase 5: Direct Approach & Precision Neutralization
- Navigate to estimated target coordinate $(\hat{x}, \hat{y})$.
- **Near-field Shortcut**: If `measure_result = "near"` ($d \le 5\,\text{m}$), bypass further measurements and trigger `/clear` immediately.
- **Execute Neutralization**:
  - **CLI**: `python3 cli.py clear <x> <y> <channel> --json`
  - **MCP**: `jammers_clear(x, y, channel)`
- **Check**:
  - If `clear_result = "success"`: Target destroyed ($t_{\text{laser}} = 2\,\text{s}$). Mark channel as cleared.
  - If `no_target_in_range`: Search optical perimeter ($R = 20\,\text{m}$ ring) or re-measure bearing.

### Phase 6: Mission Finalization
When all detected channels are cleared or session time limits approach, terminate:
- **CLI**: `python3 cli.py exit --json`
- **MCP**: `jammers_exit()`

---

## 3. Error Recovery & Fault Tolerance Matrix

| Event / Error | Root Cause | Agent Action |
| :--- | :--- | :--- |
| `connection_failed` | Simulator closed or interface not ready | Re-run `status`. Verify 5-second countdown has completed on simulator UI. |
| `measure_result: "no_signal"` | Distance $> R_{\text{recv}}$ ($1000\sim 1500\,\text{m}$) or outside $180^\circ$ directional beam | Move to opposite quadrant or sweep boundary to enter the directional beam. |
| `measure_result: "near"` | Signal overload ($d \le 5\,\text{m}$) | **Do not measure again.** Call `/clear` directly at current position. |
| `clear_result: "no_target_in_range"` | Target is $> 20\,\text{m}$ away | Move $15\,\text{m}$ along the bearing line and retry `/clear`. |
| `accepted: false` on `/enter` | Duplicate entry or expired session | Call `/exit` first to reset, then retry `/enter`. |

---

## 4. Context Pointers & Reproducible Code

- [Arena Kinematics & Physics Specification](references/simulator-spec.md): Full velocity, angle convention, and noise parameters.
- [REST API Protocol Specification](references/api-reference.md): Detailed request/response schemas and HTTP codes.
- [Minimal Agent Python Script](examples/minimal_agent_loop.py): Standalone script demonstrating programmatic exploration.
