# Jammers Simulator Arena & Kinematics Specification

This document specifies the operational environment, physical kinematics, radio direction-finding models, and action cost metrics for radio jammer search, localization, and neutralization.

---

## 1. Operational Environment & Coordinate System

### 1.1 Arena Geometry
- **Geometry**: Planar circular arena of radius $R = 1800\,\text{m}$.
- **Origin**: Center of the circular area $(0, 0)$.
- **Orientation**:
  - Positive $x$-axis points East ($0^\circ$).
  - Positive $y$-axis points North ($90^\circ$).
  - Units are in meters ($\text{m}$).
- **Boundary Behavior**: The robot may travel beyond the $1800\,\text{m}$ circular perimeter if necessary; the simulator computes movement and measurement outcomes accordingly. Coordinates must be finite floating-point values ($|x|, |y| \le 2\times 10^6\,\text{m}$).

### 1.2 Angular Convention
- $0^\circ$: Due East.
- $90^\circ$: Due North.
- $180^\circ$: Due West.
- $270^\circ$: Due South.
- Angle values are normalized to $[0, 360)^\circ$, counterclockwise positive.
- The direction-finding bearing angle $\theta_{\text{svd}}$ returned by measurements denotes the bearing toward the detected radio emitter.

### 1.3 Radio Frequency Channels & Targets
- **Channel Range**: Integers $\{1, 2, \dots, 20\}$.
- **Target Count**: $10 \le N \le 16$ active radio jammers per test run.
- **Uniqueness**: Each channel corresponds to at most one jammer.
- **Distribution**: Randomly placed within the $1800\,\text{m}$ circular arena.
- **Target Types**:
  - **Omnidirectional Jammers**: Radiate uniformly in all directions ($360^\circ$).
  - **Directional Jammers**: Radiate within a $180^\circ$ beam coverage sector (unknown main lobe orientation).

---

## 2. Electromagnetic Sensing & Physical Rules

### 2.1 Effective Reception Range
- Each radio jammer has an effective detection radius $R_{\text{recv}} \in [1000, 1500]\,\text{m}$.
- If the robot's distance to the target exceeds $R_{\text{recv}}$, no signal is detected (`no_signal`).
- For directional jammers, detection requires both:
  1. Euclidean distance $d \le R_{\text{recv}}$;
  2. The robot's position lies within the jammer's $180^\circ$ coverage sector.

### 2.2 Direction-Finding Bearing Measurement & Noise
- When a signal is detected, the direction finder measures the bearing angle $\theta_{\text{svd}}$:
  $$\theta_{\text{svd}} = (\theta_{\text{true}} + \epsilon) \pmod{360^\circ}$$
- **Measurement Noise**: $\epsilon \sim \mathcal{U}(-1^\circ, 1^\circ)$, uniformly distributed within $[-1^\circ, 1^\circ]$.
- **Precision**: Output is rounded to two decimal places.

### 2.3 Near-Field Blind Zone (Signal Overload)
- **Overload Threshold**: $d_{\text{near}} \le 5\,\text{m}$.
- When the robot is within $5\,\text{m}$ of an active jammer within its coverage angle, signal overload occurs and bearing estimation is unavailable.
- Return status: `measure_result = "near"` (indicating the robot is directly adjacent to the jammer and can immediately execute optical neutralization).

### 2.4 Optical Acquisition & Laser Neutralization
- **Effective Laser Radius**: $R_{\text{clear}} = 20\,\text{m}$.
- When the robot triggers a clear operation at position $(x, y)$ on target channel $k$:
  - If Euclidean distance $d \le 20\,\text{m}$ to target $k$, the onboard optical sensor locks on and the laser destroys the target (`clear_result = "success"`).
  - Clearance success depends strictly on distance ($d \le 20\,\text{m}$) and is independent of directional antenna orientation.
  - Each target can be cleared only once. Subsequent attempts return `no_target_in_range`.

---

## 3. Kinematics & Timing Cost Model

Actions incur virtual time penalties as follows:

| Action | Independent Command? | Cost Expression / Constant | Notes |
| :--- | :--- | :--- | :--- |
| **Mission Start** | `POST /enter` | $0\,\text{s}$ | Initializes session & virtual clock |
| **Movement** | Parameterized in `/measure`, `/clear` | $t_{\text{move}} = \frac{\Delta d}{v} = \frac{\sqrt{\Delta x^2 + \Delta y^2}}{5.0}$ | Straight-line transit at $5.0\,\text{m/s}$ |
| **Channel Switch** | Parameterized in `/measure` | $t_{\text{switch}} = \begin{cases} 1\,\text{s}, & c_{t} \ne c_{t-1} \\ 0\,\text{s}, & c_{t} = c_{t-1} \end{cases}$ | Switching between any two channels takes $1\,\text{s}$ |
| **Bearing Measurement** | `POST /measure` | $t_{\text{detect}} = 5.0\,\text{s}$ | Fixed RF integration & processing time |
| **Optical Search** | `POST /clear` | $t_{\text{opt}} = 3.0\,\text{s}$ | Fixed optical sweep duration |
| **Laser Firing** | `POST /clear` (on success) | $t_{\text{laser}} = 2.0\,\text{s}$ | Laser irradiation (total clear = $3 + 2 = 5\,\text{s}$) |
| **Mission Exit** | `POST /exit` | $0\,\text{s}$ | Finalizes session and logs |

> **Note**: The `/clear` command operates the optical/laser payload and does **not** alter the RF direction finder's tuned channel; thus, `/clear` never incurs channel-switching penalties.

---

## 4. Session Time Quotas & Constraints
- **Maximum Virtual Mission Duration**: $360,000\,\text{s}$ ($100$ hours).
- **Maximum Real Wall-Clock Duration**: $1,200\,\text{s}$ ($20$ minutes).
- Requests must be executed sequentially (one active request at a time).
