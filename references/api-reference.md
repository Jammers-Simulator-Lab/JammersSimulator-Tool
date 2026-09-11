# REST API Protocol & Interface Reference

This document specifies the HTTP RESTful communication protocol used by the autonomous quadruped robot control client and autonomous agents to communicate with the arena simulation runtime.

---

## 1. General Principles

- **Transport**: HTTP/1.1 over TCP.
- **Default Endpoint**: `http://127.0.0.1:2026` (configurable via `SIMULATOR_URL`).
- **Data Format**: `Content-Type: application/json; charset=utf-8`.
- **Concurrency**: Strict serial request pattern. Only one request may be processed at a time; pipelining or parallel dispatch is prohibited by protocol specification.

---

## 2. API Endpoints

### 2.1 POST `/enter` — Mission Initialization
Initializes the robot mission session, synchronizes system clocks, and starts virtual timing.

#### Request Schema
```json
{
  "arena_id": "default",
  "robot_id": "string",
  "request_id": "enter-1-1789052000000"
}
```

#### Response Schema
```json
{
  "accepted": true,
  "real_timestamp_ms": 1789052000100,
  "virtual_time_s": 0.0,
  "max_virtual_duration_s": 360000,
  "max_real_duration_s": 1200,
  "remaining_real_duration_s": 1200
}
```

---

### 2.2 POST `/measure` — Transit & Bearing Measurement
Directs the robot to transit from its current planar position to $(x, y)$, tune the receiver to `channel`, and collect bearing information.

#### Request Schema
```json
{
  "arena_id": "default",
  "robot_id": "string",
  "request_id": "measure-2-1789052005000",
  "position": {
    "x": 300.0,
    "y": 400.0
  },
  "channel": 1
}
```

#### Response Schema
```json
{
  "accepted": true,
  "real_timestamp_ms": 1789052005200,
  "virtual_time_s": 105.0,
  "position": {
    "x": 300.0,
    "y": 400.0
  },
  "channel": 1,
  "consumed_virtual_duration_s": 105.0,
  "cost_breakdown": {
    "movement_s": 100.0,
    "switch_channel_s": 0.0,
    "detection_s": 5.0
  },
  "measure_result": "direction",
  "svd_deg": 142.38
}
```

#### Field Explanations:
- `measure_result`:
  - `"direction"`: Signal detected. `svd_deg` contains estimated bearing angle $[0, 360)^\circ$ with noise $\epsilon \in [-1^\circ, 1^\circ]$.
  - `"near"`: Distance to target $\le 5\,\text{m}$. Receiver overloaded; `svd_deg` is omitted. Robot may immediately trigger `/clear`.
  - `"no_signal"`: No signal detected (out of range, outside $180^\circ$ directional beam, or already neutralized). `svd_deg` is omitted.

---

### 2.3 POST `/clear` — Transit & Precision Neutralization
Directs the robot to transit to $(x, y)$, activate onboard optical tracking, and neutralize the target on `channel` with high-energy laser if within range ($\le 20\,\text{m}$).

> **Important**: `/clear` does **not** switch the direction-finding channel and incurs no channel-switch cost.

#### Request Schema
```json
{
  "arena_id": "default",
  "robot_id": "string",
  "request_id": "clear-3-1789052010000",
  "position": {
    "x": 300.0,
    "y": 0.0
  },
  "channel": 3
}
```

#### Response Schema
```json
{
  "accepted": true,
  "real_timestamp_ms": 1789052010150,
  "virtual_time_s": 188.0,
  "position": {
    "x": 300.0,
    "y": 0.0
  },
  "channel": 3,
  "consumed_virtual_duration_s": 83.0,
  "cost_breakdown": {
    "movement_s": 80.0,
    "detection_s": 3.0,
    "clear_s": 0.0
  },
  "clear_result": "no_target_in_range"
}
```

#### Field Explanations:
- `clear_result`:
  - `"success"`: Target confirmed within $20\,\text{m}$ radius and destroyed ($t_{\text{opt}} = 3\,\text{s}, t_{\text{laser}} = 2\,\text{s}$).
  - `"no_target_in_range"`: Target not found within $20\,\text{m}$ ($t_{\text{opt}} = 3\,\text{s}, t_{\text{laser}} = 0\,\text{s}$).

---

### 2.4 POST `/exit` — Mission Finalization
Concludes the mission run, freezes virtual clock progression, and seals runtime logs for verification.

#### Request Schema
```json
{
  "arena_id": "default",
  "robot_id": "string",
  "request_id": "exit-4-1789052015000"
}
```

#### Response Schema
```json
{
  "accepted": true,
  "real_timestamp_ms": 1789052015050,
  "virtual_time_s": 199.0,
  "exit_reason": "user_exit"
}
```

---

## 3. Error Handling & Status Codes

- `200 OK`: Request accepted and processed. `accepted: true`.
- `400 Bad Request`: Invalid payload parameters (e.g. coordinates out of range, channel $< 1$ or $> 20$).
- `403 Forbidden`: Session inactive, expired, or invalid robot credentials.
- `500 / 503 Server Error`: Simulator internal error or engine not in testing state. Client should retry with identical `request_id`.
