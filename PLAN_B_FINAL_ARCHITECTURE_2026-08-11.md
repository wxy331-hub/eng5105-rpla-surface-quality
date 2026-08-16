# ENG5105 Final Plan B Architecture Decision

**Decision date:** 11 August 2026  
**Status:** Active project baseline

## Decision

The school will provide the Raspberry Pi 4, STM32 Nucleo-L432KC, and XIAO
ESP32S3 Sense with OV3660 camera. It will not provide the additional camera
materials required for Plan A. The project therefore adopts Plan B as the final
implementation and validation path. Plan A remains only as a concept comparison.

## Final system boundary

```text
rPLA filament + controlled lighting
    -> ESP32S3 OV3660 camera (SVGA 800x600 MJPEG acquisition)
    -> controlled 2.4 GHz Wi-Fi
    -> Raspberry Pi 4
         - resident Python/OpenCV inspection service
         - REST API and WebSocket
         - SQLite evidence database
         - web GUI
    <-> STM32 Nucleo-L432KC
         - encoder counting and position timing
         - Raspberry Pi heartbeat watchdog
         - lighting control
         - safe actuator/marker interface
```

The camera continues to stream live images. Raspberry Pi 4 moves the processing
and service workload off the demonstration laptop; STM32 adds deterministic
real-time I/O and fail-safe behaviour. Neither board replaces the camera.

## Evidence already available

- Physical OV3660 identity and MJPEG connectivity have been confirmed.
- The Windows development system has a resident Python detection service,
  REST API, WebSocket updates, SQLite records, and GUI integration.
- SVGA 800x600 is the selected live resolution.
- Software recovery, latest-frame buffering, record deletion, and network-fault
  behaviour have implementation evidence.

These results prove integration behaviour only. They do not prove rPLA defect
accuracy, physical defect size, physical position, or final usable line speed.

## Work that can be completed before real material testing

1. Keep all GUI and documentation labels aligned to the final Plan B system.
2. Prepare Raspberry Pi installation, service startup, API, database, and GUI deployment.
3. Define the Pi-STM32 serial message schema, heartbeat, encoder, and safe-state contracts.
4. Keep the GUI in candidate-event mode and show only pixel measurements until calibration.
5. Prepare repeatable latency, network-loss, recovery, database, and export tests.

## Work that requires the physical fixture and real rPLA material

1. Fix camera distance, focus, lighting, background, and the final inspection ROI.
2. Re-test sustained FPS, post-decode-to-GUI latency, image clarity, and candidate stability at 800x600.
3. Calibrate pixels per millimetre and encoder counts per millimetre.
4. Collect labelled normal and defective material by batch or spool.
5. Validate false alarms, missed detections, precision, recall, F1 score, minimum detectable defect, and usable line speed.
6. Verify STM32 watchdog and any actuator output on real wiring before enabling automatic actions.

## Publication hold

Do not publish the current state to GitHub as the final project result. Update the
public repository only after the real-material evidence has been reviewed and the
final displayed data has been accepted.
