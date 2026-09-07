# Procurement Evidence and Cost Basis

**Compiled:** 22 August 2026
**Currency:** Australian dollars, GST included unless stated otherwise. Shipping excluded.
**Standing:** this file records what the team can show. Nothing here is a purchase order, and no
line is claimed as a quotation unless a supplier document is named against it.

## 1. Known figures

| Item | Quantity | Cost | Standing of the figure | Source of record |
|---|---:|---:|---|---|
| 4K integrated inspection camera, IMX415 sensor, adjustable field, integral illuminator and stand | 1 | A$142.00 | Approved; not yet ordered. Price obtained through the team's own supply channel. | Team supply channel. Package contents and sensor identity cross-checked against the public listing (Banggood, 2026); sensor parameters taken from the manufacturer data sheet, not the listing. |
| LED strip lighting set | 1 set | A$18.00 | Already purchased and held by the team. No further procurement. | Team record of the existing purchase. |
| **Known subtotal** |  | **A$160.00** | One approved price and one item already paid for | — |

The camera is the only concept-specific purchase in the selected build. Everything else in the
build is either supplied by the university or common to both acquisition chains.

### Evidence that must be retained before the order is placed

A live retail product page is not durable evidence. Its stock state, shipping options and price
change without notice, and the page keeps no record of what it said on the day it was read. The
following must therefore be captured and stored in the evidence bank, dated, before commitment:

1. A dated screenshot or a formal quotation showing the price actually offered.
2. A dated record of availability and the delivery estimate from the channel used.
3. Confirmation that the device presents a standard USB video-class interface to Linux on the
   Raspberry Pi 4. The public listing names Windows and macOS only, and a supplier assurance is
   not a test.
4. Confirmation that the field adjustment is optical rather than a digital crop, because the
   sampling density in Section 5.2 of the report assumes it.

Items 3 and 4 are technical gates, not commercial ones. Failing either invalidates the optical
argument for the selected concept, so both are checked before the order rather than after
delivery.

## 2. Planning allowances for the unquoted groups

None of the five groups below has been quoted. Each carries a team planning allowance: a
budgeting range the team is prepared to defend for that class of part, stated with its basis and
its uncertainty, and replaced by a dated supplier record before the item is committed.

| Group | Planning allowance | Basis | What decides where it lands |
|---|---:|---|---|
| Enclosed 12 V DC supply with screw terminals, 5 V conversion, MOSFET drivers, fuses, connectors and protection | A$80.00–120.00 | Team allowance for an Australian-sourced set | Final current ratings, the number of protected switching channels, and whether a pre-assembled enclosed supply or discrete parts are used |
| Enclosure, camera bracket and indexed sample holder | A$40.00–90.00 | Team allowance | Enclosure size, which follows the camera's working distance; the rotational indexing mechanism carries the upper end |
| Diffuser, crossed-polariser set and illumination reference detector for the LED strip | A$30.00–70.00 | Team allowance | Film sizes, which follow the optical head geometry; whether polariser film of adequate extinction is needed on both source and lens; and whether the issued kit contains a spare photodiode for the reference detector |
| Optical calibration set: graduated scale, resolution target, dark and white references | A$40.00–90.00 | Team allowance | Target grade. A printed target sits at the lower end; a chrome-on-glass stage micrometre or a certified resolution target sits at the upper end |
| Reject/stop demonstrator | A$10.00–25.00 | Team allowance | Whether the demonstrator is an indicator only or a small actuated device |
| **Allowance subtotal** | **A$200.00–395.00** | Five allowances, no quotations | — |

## 3. Build cost as stated in the report

| Aggregate | Figure | Composition |
|---|---:|---|
| Additional procurement | A$342.00–537.00 | Camera A$142.00 plus the five allowances |
| Build total | A$360.00–555.00 | Additional procurement plus the LED strip already paid for at A$18.00 |
| University-supplied equipment | A$0 | Raspberry Pi 4 set, STM32 Nucleo-L432KC, XIAO ESP32S3 Sense, the SFH4555/BPW46/LM324N channel with the MCP3208 spare, and the issued passives and prototyping parts |

The width of the range is a property of the evidence, not a hedge. Five of the seven charged
lines have no quotation behind them, and a quotation can land outside an allowance. The totals
are restated once quotations exist rather than carried forward as though they had been prices.

Physical issue, condition and compatibility of the university-supplied parts still require an
incoming check before any of them is relied on.

## 4. What this file does not establish

- No purchase order has been raised for any line.
- No delivered lead time has been established for the camera or for any allowance group.
- The allowances are not supplier figures and must not be quoted as if they were.
- Availability observed on any given day does not survive as evidence unless it was captured as a
  dated screenshot or quotation.
