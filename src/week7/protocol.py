"""Bounded JSON simulation of the Week 7 lighting handshake.

This module has no serial transport and never enables physical outputs. Times are
local monotonic seconds: a remote timestamp cannot renew the heartbeat lease.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping
from typing import Any


MAX_MESSAGE_BYTES = 4096
LIGHTING_MODES = ("bright_field", "dark_field")
ANGLES_DEG = (0, 60, 120, 180, 240, 300)
EVIDENCE_LEVEL = "OFFLINE_SYNTHETIC_ONLY"


class ProtocolError(ValueError):
    """A message or capture did not satisfy the simulated safety contract."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def encode_message(message: Mapping[str, Any]) -> str:
    """Encode one newline-delimited JSON object, rejecting nonfinite numbers."""
    if not isinstance(message, Mapping):
        raise ProtocolError("message must be an object")
    try:
        encoded = json.dumps(dict(message), allow_nan=False, separators=(",", ":")) + "\n"
    except (TypeError, ValueError, RecursionError) as exc:
        raise ProtocolError("message must contain finite JSON values") from exc
    if len(encoded.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message exceeds 4096 bytes")
    return encoded


def decode_message(message: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
    """Decode one bounded JSON object; reject duplicate keys and NaN/Infinity."""
    if isinstance(message, Mapping):
        message = encode_message(message)
    if isinstance(message, bytes):
        if len(message) > MAX_MESSAGE_BYTES:
            raise ProtocolError("message exceeds 4096 bytes")
        try:
            message = message.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("message must be UTF-8") from exc
    if not isinstance(message, str):
        raise ProtocolError("message must be JSON text or an object")
    try:
        byte_length = len(message.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ProtocolError("message must contain valid Unicode") from exc
    if byte_length > MAX_MESSAGE_BYTES:
        raise ProtocolError("message exceeds 4096 bytes")
    try:
        parsed = json.loads(
            message,
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ProtocolError(f"nonfinite JSON number: {value}")
            ),
        )
    except (ValueError, RecursionError) as exc:
        raise ProtocolError(f"invalid JSON message: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProtocolError("message must be a JSON object")
    return parsed


def _identifier(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ProtocolError(f"{name} must be a nonempty string of at most 128 characters")
    return value


def _number(value: Any, name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ProtocolError(f"{name} must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ProtocolError(f"{name} exceeds finite numeric range") from exc
    if not finite or value < minimum:
        raise ProtocolError(f"{name} must be finite and >= {minimum}")
    return float(value)


class SimulatedLightingController:
    """One frame per request, with explicit OFF acknowledgement between requests.

    ``begin`` returns a simulated command. A matching ``receive`` status grants
    readiness; ``authorize_frame`` checks the frame was acquired during that
    readiness lease. ``finish`` or ``reset`` always requests OFF, including after
    a failure. Callers must acknowledge OFF before beginning another branch.
    """

    def __init__(
        self,
        session_id: str,
        *,
        clock: Callable[[], float] = time.monotonic,
        ready_timeout_s: float = 2.0,
        heartbeat_timeout_s: float = 1.0,
    ) -> None:
        self.session_id = _identifier(session_id, "session_id")
        self.clock = clock
        self.ready_timeout_s = _number(ready_timeout_s, "ready_timeout_s")
        self.heartbeat_timeout_s = _number(heartbeat_timeout_s, "heartbeat_timeout_s")
        if not self.ready_timeout_s or not self.heartbeat_timeout_s:
            raise ProtocolError("timeouts must be positive")
        self.state = "OFF"
        self.request_id: str | None = None
        self.lighting_mode = "OFF"
        self.angle_deg: int | None = None
        self.last_rx_seq = -1
        self._tx_seq = 0
        self._used_request_ids: set[str] = set()
        self._started_at: float | None = None
        self._ready_at: float | None = None
        self._heartbeat_at: float | None = None
        self._last_clock: float | None = None
        self._status: dict[str, Any] | None = None
        self._frame_authorized = False

    @property
    def outputs_enabled(self) -> bool:
        """The simulator provides no hardware output path."""
        return False

    def _now(self) -> float:
        now = _number(self.clock(), "local monotonic clock")
        if self._last_clock is not None and now < self._last_clock:
            self.state = "BLOCKED"
            raise ProtocolError("local monotonic clock moved backwards")
        self._last_clock = now
        return now

    def _command(self, action: str) -> dict[str, Any]:
        self._tx_seq += 1
        return {
            "schema_version": 1,
            "type": "command",
            "transport": "SIMULATED",
            "session_id": self.session_id,
            "request_id": self.request_id,
            "seq": self._tx_seq,
            "action": action,
            "lighting_mode": self.lighting_mode,
            "angle_deg": self.angle_deg,
            "outputs_enabled": False,
            "evidence_level": EVIDENCE_LEVEL,
        }

    def begin(self, mode: str, request_id: str, *, angle_deg: int | None = None) -> dict[str, Any]:
        if self.state != "OFF":
            raise ProtocolError("explicit OFF acknowledgement required before next branch")
        if mode not in LIGHTING_MODES:
            raise ProtocolError("unsupported lighting_mode")
        request_id = _identifier(request_id, "request_id")
        if request_id in self._used_request_ids:
            raise ProtocolError("request_id already used in this session")
        if angle_deg is not None and (type(angle_deg) is not int or angle_deg not in ANGLES_DEG):
            raise ProtocolError("angle_deg must be one of the six indexed angles")
        now = self._now()
        self.request_id = request_id
        self.lighting_mode = mode
        self.angle_deg = angle_deg
        self._used_request_ids.add(request_id)
        self._started_at = now
        self._ready_at = None
        self._heartbeat_at = None
        self._status = None
        self._frame_authorized = False
        self.state = "WAIT_READY"
        return self._command("SET_LIGHTING")

    def make_status(
        self,
        *,
        ready: bool = True,
        material_present: bool = True,
        reference_ok: bool = True,
        fault: str | None = None,
        heartbeat: bool = True,
        driver_value: float | None = None,
        reference_reading: float = 1.0,
    ) -> dict[str, Any]:
        """Build a deterministic peer message for simulation and fault injection.

        Driver values are dimensionless simulated values, never measured PWM,
        current or illuminance. The helper does not itself grant readiness.
        """
        if self.request_id is None:
            raise ProtocolError("begin or reset a request before making a status")
        return {
            "schema_version": 1,
            "type": "status",
            "transport": "SIMULATED",
            "session_id": self.session_id,
            "request_id": self.request_id,
            "seq": self.last_rx_seq + 1,
            "lighting_mode": self.lighting_mode,
            "angle_deg": self.angle_deg,
            "ready": ready,
            "material_present": material_present,
            "reference_ok": reference_ok,
            "fault": fault,
            "driver_value": (0.0 if self.lighting_mode == "OFF" else 0.5)
            if driver_value is None else driver_value,
            "reference_reading": reference_reading,
            "heartbeat": heartbeat,
            "outputs_enabled": False,
        }

    def _validate_status(self, value: dict[str, Any]) -> None:
        expected = {
            "schema_version", "type", "transport", "session_id", "request_id", "seq",
            "lighting_mode", "angle_deg", "ready", "material_present", "reference_ok",
            "fault", "driver_value", "reference_reading", "heartbeat", "outputs_enabled",
        }
        if set(value) != expected:
            raise ProtocolError("status schema fields do not match version 1")
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ProtocolError("unsupported schema_version")
        if value["type"] != "status" or value["transport"] != "SIMULATED":
            raise ProtocolError("only SIMULATED status messages are accepted")
        if value["outputs_enabled"] is not False:
            raise ProtocolError("physical outputs are permanently disabled")
        for key in ("ready", "material_present", "reference_ok", "heartbeat"):
            if type(value[key]) is not bool:
                raise ProtocolError(f"{key} must be boolean")
        if value["fault"] is not None:
            _identifier(value["fault"], "fault")
        for key in ("session_id", "request_id"):
            _identifier(value[key], key)
            if value[key] != getattr(self, key):
                raise ProtocolError(f"{key} mismatch")
        if type(value["seq"]) is not int or value["seq"] < 0:
            raise ProtocolError("seq must be a nonnegative integer")
        if value["seq"] <= self.last_rx_seq:
            raise ProtocolError("stale or duplicate seq")
        if value["lighting_mode"] != self.lighting_mode:
            raise ProtocolError("lighting_mode mismatch")
        if value["angle_deg"] is not None and type(value["angle_deg"]) is not int:
            raise ProtocolError("angle_deg must be an integer or null")
        if value["angle_deg"] != self.angle_deg:
            raise ProtocolError("angle_deg mismatch")
        driver = _number(value["driver_value"], "driver_value")
        if driver > 1:
            raise ProtocolError("driver_value must be a normalized value <= 1")
        _number(value["reference_reading"], "reference_reading")
        if self.lighting_mode == "OFF" and driver != 0:
            raise ProtocolError("OFF acknowledgement requires zero driver_value")
        if self.lighting_mode != "OFF" and value["ready"] and driver == 0:
            raise ProtocolError("lighting readiness requires nonzero simulated driver_value")

    def receive(self, message: str | bytes | Mapping[str, Any]) -> dict[str, Any]:
        if self.state == "OFF":
            raise ProtocolError("no active request")
        try:
            value = decode_message(message)
            self._validate_status(value)
            now = self._now()
        except ProtocolError:
            # A malformed/replayed status cannot leave the prior READY lease live.
            if self.state != "WAIT_OFF":
                self.state = "BLOCKED"
            raise
        self.last_rx_seq = value["seq"]
        self._status = value
        if self.state == "WAIT_OFF":
            if value["fault"] is not None or not value["ready"]:
                raise ProtocolError("OFF acknowledgement must be ready and fault-free")
            self.state = "OFF"
            self._ready_at = None
            self._heartbeat_at = None
            return dict(value)
        if self.state == "BLOCKED":
            raise ProtocolError("controller is blocked; request OFF before recovery")
        if self._started_at is None or now - self._started_at >= self.ready_timeout_s:
            self.state = "BLOCKED"
            raise ProtocolError("capture readiness timeout")
        if self._heartbeat_at is not None and now - self._heartbeat_at >= self.heartbeat_timeout_s:
            self.state = "BLOCKED"
            raise ProtocolError("heartbeat stale; request OFF before recovery")
        if value["heartbeat"]:
            self._heartbeat_at = now
        if value["fault"] is not None:
            self.state = "BLOCKED"
            raise ProtocolError(f"controller fault: {value['fault']}")
        if not all(value[key] for key in ("ready", "material_present", "reference_ok")):
            self.state = "WAIT_READY"
            self._ready_at = None
        else:
            if self.state != "READY":
                self._ready_at = now
            self.state = "READY"
        return dict(value)

    def authorize_frame(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        now = self._now()
        if self.state != "READY" or self._status is None or self._ready_at is None:
            raise ProtocolError("capture requires ready, material_present and reference_ok")
        if self._started_at is None or now - self._started_at >= self.ready_timeout_s:
            self.state = "BLOCKED"
            raise ProtocolError("capture readiness timeout")
        if self._heartbeat_at is None or now - self._heartbeat_at >= self.heartbeat_timeout_s:
            self.state = "BLOCKED"
            raise ProtocolError("heartbeat stale")
        if not isinstance(metadata, Mapping):
            raise ProtocolError("frame metadata must be an object")
        for key in ("session_id", "request_id", "lighting_mode"):
            if metadata.get(key) != getattr(self, key):
                raise ProtocolError(f"frame {key} mismatch")
        if "angle_deg" in metadata:
            angle = metadata["angle_deg"]
            if (angle is not None and type(angle) is not int) or angle != self.angle_deg:
                raise ProtocolError("frame angle_deg mismatch")
        frame_id = metadata.get("frame_id")
        if not ((type(frame_id) is int and frame_id >= 0) or
                (isinstance(frame_id, str) and frame_id.strip() and len(frame_id) <= 128)):
            raise ProtocolError("frame_id must be a nonnegative integer or nonempty identifier")
        captured = _number(metadata.get("captured_monotonic"), "captured_monotonic")
        if captured < self._ready_at or captured > now:
            raise ProtocolError("frame timestamp outside the current ready capture window")
        if self._frame_authorized:
            raise ProtocolError("one frame already authorized for this request")
        self._frame_authorized = True
        return {
            **dict(self._status),
            "frame_id": frame_id,
            "captured_monotonic": captured,
            "authorized_monotonic": now,
            "evidence_level": EVIDENCE_LEVEL,
            "outputs_enabled": False,
        }

    def finish(self) -> dict[str, Any]:
        """Request OFF even after a failed capture; recovery needs a fresh ACK."""
        if self.request_id is None:
            self.request_id = f"off-{self._tx_seq + 1}"
            self._used_request_ids.add(self.request_id)
        self.lighting_mode = "OFF"
        self.state = "WAIT_OFF"
        self._ready_at = None
        self._heartbeat_at = None
        return self._command("OFF")

    def reset(self) -> dict[str, Any]:
        """Explicit manual recovery; sequence and used-request history survive."""
        return self.finish()
