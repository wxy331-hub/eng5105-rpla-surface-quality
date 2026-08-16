# Proposal-Stage Engineering Calculations

All values below are design allocations or calculations from recorded integration observations. They are not measured final-hardware power, calibrated physical performance, or stakeholder-approved requirements.

## 1. Frame spacing along a moving filament

The axial travel between processed frames is

\[
\Delta x = \frac{v}{f},
\]

where \(v\) is line speed in mm/s and \(f\) is processed frames/s.

| Line speed | Speed in mm/s | At observed 10.77 FPS | At proposed 20 FPS |
|---:|---:|---:|---:|
| 1 m/min | 16.67 | 1.55 mm/frame | 0.83 mm/frame |
| 3 m/min | 50.00 | 4.64 mm/frame | 2.50 mm/frame |
| 5 m/min | 83.33 | 7.74 mm/frame | 4.17 mm/frame |

The calculation does not establish a detectable defect size. It shows why the current SVGA throughput result does not satisfy the proposed 20 FPS target and why line speed, field of view, exposure, and multi-frame confirmation must be tested together.

## 2. Alarm-delay travel

The distance travelled during an alarm delay is

\[
d = v t.
\]

At 5 m/min, the filament moves 41.67 mm in the proposed 500 ms alarm window. At 1 m/min it moves 8.33 mm. The recorded 222.99 ms P95 brightness-step response corresponds mathematically to 18.58 mm at 5 m/min, but that test does not include a sensor-exposure timestamp or browser-paint completion and therefore is not used as final physical latency evidence.

## 3. Encoder scale

For a 400 pulse/revolution quadrature encoder decoded on four edges, the theoretical count is 1600 counts/revolution. If the measured effective wheel circumference is \(C\) mm,

\[
k_e = \frac{1600}{C}\;\text{counts/mm}, \qquad
q_e = \frac{C}{1600}\;\text{mm/count}.
\]

No value is assigned to \(C\) before the physical wheel and contact geometry are measured. Slip, eccentricity, preload, and camera-to-marker offset must be included in the position-error test rather than inferred from encoder resolution alone.

## 4. Optical scale

If a reference of known length \(L_{ref}\) mm spans \(P_{ref}\) pixels in the final filament plane,

\[
s = \frac{L_{ref}}{P_{ref}}\;\text{mm/pixel}, \qquad
L_{candidate} = s P_{candidate}.
\]

The scale is valid only for the fixed focus, working distance, ROI, and optical geometry used during calibration. Until a `calibration_id` exists, `size_mm` remains null.

## 5. Proposed power budget

### 5.1 Raspberry Pi supply domain

| Load | Normal allocation | Peak allocation |
|---|---:|---:|
| Raspberry Pi 4 | 7.50 W | 12.50 W |
| STM32 Nucleo via USB | 0.25 W | 0.50 W |
| **Domain total** | **7.75 W** | **13.00 W** |

For a 5.1 V, 3 A Raspberry Pi supply, available power is

\[
P_{available}=5.1\times3=15.3\;\text{W}.
\]

The design peak margin is

\[
M=\frac{15.3-13.0}{15.3}\times100=15.0\%.
\]

This margin must be checked using undervoltage logs and measured current on the deployed Raspberry Pi. Motors and lighting are excluded from this domain.

### 5.2 Auxiliary 12 V domain

| Load | Normal allocation | Peak allocation | Conversion path |
|---|---:|---:|---|
| ESP32S3 Sense + OV3660 | 1.50 W | 2.50 W | 12 V to regulated 5 V |
| IR/analogue/LCD electronics | 0.40 W | 0.80 W | 12 V to regulated 5 V |
| Controlled lighting | 8.00 W | 12.00 W | 12 V branch |
| Encoder | 0.50 W | 1.20 W | Rated branch after component confirmation |
| Marker/servo demonstrator | 0 W | 5.00 W | Protected switched branch |

Assuming 85% conversion efficiency for the 5 V loads, the 12 V input demand is

\[
P_{12V,normal}=\frac{1.50+0.40}{0.85}+8.00+0.50=10.74\;\text{W},
\]

\[
P_{12V,peak}=\frac{2.50+0.80}{0.85}+12.00+1.20+5.00=22.08\;\text{W}.
\]

A regulated 12 V, 3 A supply provides 36 W. Its proposal-stage peak margin is

\[
M=\frac{36-22.08}{36}\times100=38.7\%.
\]

Final supply, fuse, conductor, connector, and thermal selections require inrush and steady-state measurements. Each switched inductive branch requires appropriate flyback suppression; the Raspberry Pi must not power the marker/servo.

## 6. Photodiode conditioning basis

For a photodiode current \(I_{PD}\) and desired output swing \(V_{span}\), the first transimpedance estimate is

\[
R_f=\frac{V_{span}}{I_{PD}}.
\]

With feedback capacitance \(C_f\), the approximate low-pass corner is

\[
f_c=\frac{1}{2\pi R_f C_f}.
\]

The project has not yet measured \(I_{PD}\) under the final geometry. Numerical resistor and capacitor values are therefore intentionally deferred until the optical head is assembled; assigning them now would create false precision.

