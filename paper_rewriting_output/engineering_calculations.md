# Proposal-Stage Engineering Calculations

Every value below is a design allocation or an arithmetic consequence of one. None
is measured final-hardware power, calibrated optical performance, or a
stakeholder-approved requirement. The report is the authoritative statement of each
of these; this file exists so the arithmetic can be checked in one place.

The design images a held, indexed filament specimen rather than a running strand,
so there is no line-speed, frame-spacing or encoder-scale calculation here. What
replaces them is the sampling-density and depth-of-field pair in Section 1, which is
what forced the specimen to be held in the first place.

## 1. Optical sampling density and the depth of field it costs

For a horizontal pixel count \(N_h\) spread over an imaged field width \(w_f\), the
sampling density \(s\) and the pixel span of a feature of width \(d\) are

\[
s=\frac{N_h}{w_f}, \qquad n_d=s\,d.
\]

At the planned working point, \(N_h = 3840\) and \(w_f = 40\) mm:

| Quantity | Value |
|---|---:|
| Sampling density \(s\) | 96 px/mm |
| 1.75 mm strand | 168 px |
| 0.20 mm R2 target feature | 19 px |

Sampling density is not resolving power. The module publishes no working aperture,
and its field adjustment may combine optical and electronic zoom, so the delivered
detail can sit well below what the pixel count suggests. G3 measures it against a
resolution target rather than assuming it.

Narrowing the field to reach that density costs depth of field. A first-order
estimate at an assumed f/4 working aperture leaves roughly 1.4 mm of total focus
depth. A cylinder of radius \(R\) consumes, across the usable \(\pm45°\) arc,

\[
\Delta z = R\left(1-\cos 45°\right) = 0.875 \times 0.293 = 0.26\ \text{mm}.
\]

That leaves margin for a specimen a fixture holds on the optical axis, and none for
a strand free to wander. This is the calculation the held-specimen design basis
rests on.

## 2. Circumferential coverage

One camera sees one arc. A single view reads a usable arc of about \(\pm45°\)
before the surface turns too far from the optical axis, so four positions at 90°
would meet edge to edge with no overlap and no tolerance for placement error. Six
positions at 60° are planned instead, leaving about 30° of overlap. Each position is
captured under both illumination branches, so one specimen yields twelve views and
one merged event set.

## 3. Optical scale

If a reference of known length \(L_{ref}\) mm spans \(P_{ref}\) pixels in the final
filament plane,

\[
s = \frac{L_{ref}}{P_{ref}}\;\text{mm/pixel}, \qquad
L_{candidate} = s P_{candidate}.
\]

The scale is valid only for the fixed focus, working distance, ROI and optical
geometry used during calibration, and only for the acquisition chain it was measured
on. Until a `calibration_id` exists, `size_mm` remains null.

## 4. Proposed power budget

### 4.1 Raspberry Pi supply domain

| Load | Normal allocation | Peak allocation |
|---|---:|---:|
| Raspberry Pi 4 | 7.50 W | 12.50 W |
| STM32 Nucleo via USB | 0.25 W | 0.50 W |
| **Domain total** | **7.75 W** | **13.00 W** |

For a 5.1 V, 3 A supply, available power is

\[
P_{available}=5.1\times3=15.3\;\text{W},
\]

and the design peak margin is

\[
M=\frac{15.3-13.0}{15.3}\times100=15.0\%.
\]

The selected camera is assumed to run from the mains adapter its package includes,
so it appears in neither domain total. If incoming inspection finds it bus-powered,
a Raspberry Pi 4 USB port rated at 900 mA adds up to 4.50 W, taking the peak
allocation to 17.50 W against 15.30 W available. That is a negative margin, so a
bus-powered device forces a larger supply or a self-powered hub before the fixture is
wired.

### 4.2 Auxiliary 12 V domain

| Load | Normal allocation | Peak allocation | Conversion path |
|---|---:|---:|---|
| ESP32S3 Sense + OV3660 | 1.50 W | 2.50 W | 12 V to regulated 5 V |
| IR/analogue/LCD electronics | 0.40 W | 0.80 W | Mixed regulated rails |
| Controlled lighting | 8.00 W | 12.00 W | 12 V branch |
| Reject/stop demonstrator | 0 W | 5.00 W | Protected switched branch |

Assuming 85% conversion efficiency for the 5 V loads,

\[
P_{12V,normal}=\frac{1.50+0.40}{0.85}+8.00=10.24\;\text{W},
\]

\[
P_{12V,peak}=\frac{2.50+0.80}{0.85}+12.00+5.00=20.88\;\text{W}.
\]

A regulated 12 V, 5 A source supplies 60 W, so the proposal-stage peak margin is

\[
M=\frac{60-20.88}{60}\times100=65.2\%.
\]

Final supply, fuse, conductor, connector and thermal selections require inrush and
steady-state measurements. Each switched inductive branch requires appropriate
flyback suppression, and the Raspberry Pi must not power the demonstrator.

## 5. Photodiode conditioning basis

For a photodiode current \(I_{PD}\) and a desired output swing \(V_{span}\), the
first transimpedance estimate is

\[
R_f=\frac{V_{span}}{I_{PD}}.
\]

With feedback capacitance \(C_f\), the approximate low-pass corner is

\[
f_c=\frac{1}{2\pi R_f C_f}.
\]

\(I_{PD}\) has not been measured under the final geometry, so resistor and capacitor
values are deferred until the optical head is assembled; assigning them now would
create false precision.

Two conditioning stages are needed rather than one, and the same two equations size
both. The infrared presence-and-health channel is sampled only with both
illumination branches de-energised, which keeps it an infrared measurement. The
illumination reference detector watches the diffuser output on its own stage and its
own converter channel, because one detector cannot separate a change in lamp output
from a change in what sits in front of the lens.
