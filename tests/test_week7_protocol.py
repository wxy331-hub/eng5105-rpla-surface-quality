import json

import pytest

from src.week7.protocol import (
    ANGLES_DEG,
    LIGHTING_MODES,
    ProtocolError,
    SimulatedLightingController,
    decode_message,
    encode_message,
)


class Clock:
    def __init__(self):
        self.value = 10.0

    def __call__(self):
        return self.value


@pytest.fixture
def gate():
    clock = Clock()
    controller = SimulatedLightingController("session-test", clock=clock)
    return controller, clock


def frame(controller, clock, **overrides):
    return {
        "session_id": controller.session_id,
        "request_id": controller.request_id,
        "lighting_mode": controller.lighting_mode,
        "frame_id": 1,
        "captured_monotonic": clock(),
        **overrides,
    }


def ready(controller):
    controller.begin("bright_field", "cycle-1", angle_deg=0)
    controller.receive(encode_message(controller.make_status()))


def off(controller):
    command = controller.finish()
    assert command["lighting_mode"] == "OFF"
    assert command["outputs_enabled"] is False
    controller.receive(encode_message(controller.make_status()))


def test_all_twelve_branches_require_explicit_off_and_unique_requests(gate):
    controller, clock = gate
    rx_sequences = []
    tx_sequences = []
    for angle in ANGLES_DEG:
        for mode in LIGHTING_MODES:
            command = controller.begin(mode, f"capture-{angle}-{mode}", angle_deg=angle)
            tx_sequences.append(command["seq"])
            assert command["outputs_enabled"] is False
            assert command["transport"] == "SIMULATED"
            with pytest.raises(ProtocolError, match="requires ready"):
                controller.authorize_frame(frame(controller, clock))
            status = controller.receive(encode_message(controller.make_status()))
            rx_sequences.append(status["seq"])
            proof = controller.authorize_frame(frame(controller, clock))
            assert proof["lighting_mode"] == mode
            assert proof["evidence_level"] == "OFFLINE_SYNTHETIC_ONLY"
            assert proof["outputs_enabled"] is False
            with pytest.raises(ProtocolError, match="already authorized"):
                controller.authorize_frame(frame(controller, clock, frame_id=2))
            with pytest.raises(ProtocolError, match="OFF acknowledgement"):
                controller.begin("dark_field", "premature")
            tx_sequences.append(controller.finish()["seq"])
            with pytest.raises(ProtocolError, match="OFF acknowledgement"):
                controller.begin("dark_field", "premature")
            rx_sequences.append(controller.receive(controller.make_status())["seq"])
    assert rx_sequences == list(range(24))
    assert tx_sequences == list(range(1, 25))


@pytest.mark.parametrize("field,value", [
    ("session_id", "old-session"),
    ("request_id", "old-cycle"),
    ("lighting_mode", "dark_field"),
    ("angle_deg", 60),
    ("angle_deg", False),
    ("seq", True),
    ("seq", -1),
    ("ready", 1),
    ("material_present", "true"),
    ("reference_ok", None),
    ("heartbeat", 1),
    ("outputs_enabled", True),
    ("transport", "SERIAL"),
    ("schema_version", True),
    ("driver_value", 2.0),
    ("driver_value", 0),
    ("reference_reading", -1.0),
    ("reference_reading", 10 ** 1000),
    ("fault", ""),
])
def test_bad_status_revokes_a_previous_ready_lease(gate, field, value):
    controller, clock = gate
    ready(controller)
    status = controller.make_status()
    status[field] = value
    with pytest.raises(ProtocolError):
        controller.receive(status)
    assert controller.state == "BLOCKED"
    with pytest.raises(ProtocolError):
        controller.authorize_frame(frame(controller, clock))
    off(controller)
    controller.begin("dark_field", "cycle-recovered")


@pytest.mark.parametrize("field", ["ready", "material_present", "reference_ok"])
def test_each_interlock_blocks_capture(gate, field):
    controller, clock = gate
    controller.begin("bright_field", "cycle-1")
    status = controller.make_status()
    status[field] = False
    controller.receive(status)
    with pytest.raises(ProtocolError, match="requires ready"):
        controller.authorize_frame(frame(controller, clock))
    assert controller.outputs_enabled is False


def test_fault_latches_until_explicit_off_recovery(gate):
    controller, clock = gate
    ready(controller)
    with pytest.raises(ProtocolError, match="fault"):
        controller.receive(controller.make_status(fault="overtemperature_simulated"))
    with pytest.raises(ProtocolError, match="blocked"):
        controller.receive(controller.make_status())
    controller.reset()
    controller.receive(controller.make_status())
    controller.begin("bright_field", "cycle-2")


@pytest.mark.parametrize("seq", [0, -1])
def test_duplicate_and_old_sequence_do_not_refresh_heartbeat(gate, seq):
    controller, clock = gate
    ready(controller)
    clock.value += 0.5
    message = controller.make_status()
    message["seq"] = seq
    with pytest.raises(ProtocolError):
        controller.receive(message)
    assert controller.last_rx_seq == 0
    assert controller.state == "BLOCKED"


def test_request_ids_and_sequence_history_survive_reset(gate):
    controller, clock = gate
    ready(controller)
    old_status = controller.make_status()
    off(controller)
    with pytest.raises(ProtocolError, match="already used"):
        controller.begin("bright_field", "cycle-1")
    controller.begin("dark_field", "cycle-2")
    with pytest.raises(ProtocolError, match="request_id mismatch"):
        controller.receive(old_status)


def test_heartbeat_stale_at_exact_deadline_blocks_capture(gate):
    controller, clock = gate
    ready(controller)
    clock.value += 1.0
    with pytest.raises(ProtocolError, match="heartbeat stale"):
        controller.authorize_frame(frame(controller, clock))
    assert controller.state == "BLOCKED"


def test_no_heartbeat_blocks_capture_even_when_ready(gate):
    controller, clock = gate
    controller.begin("bright_field", "cycle-1")
    controller.receive(controller.make_status(heartbeat=False))
    with pytest.raises(ProtocolError, match="heartbeat stale"):
        controller.authorize_frame(frame(controller, clock))


def test_late_heartbeat_requires_off_recovery_instead_of_reviving_old_lease(gate):
    controller, clock = gate
    ready(controller)
    clock.value += 1.0
    with pytest.raises(ProtocolError, match="heartbeat stale"):
        controller.receive(controller.make_status())
    assert controller.state == "BLOCKED"
    off(controller)
    controller.begin("dark_field", "cycle-2")
    controller.receive(controller.make_status())
    controller.authorize_frame(frame(controller, clock))


def test_fresh_heartbeat_does_not_extend_capture_deadline(gate):
    controller, clock = gate
    ready(controller)
    clock.value += 0.8
    controller.receive(controller.make_status())
    clock.value += 0.8
    controller.receive(controller.make_status())
    clock.value = 12.0
    with pytest.raises(ProtocolError, match="timeout"):
        controller.authorize_frame(frame(controller, clock))


def test_late_ready_message_cannot_revive_expired_request(gate):
    controller, clock = gate
    controller.begin("bright_field", "cycle-1")
    clock.value += 2.0
    with pytest.raises(ProtocolError, match="timeout"):
        controller.receive(controller.make_status())
    off(controller)


@pytest.mark.parametrize("metadata", [
    {"session_id": "other"},
    {"request_id": "other"},
    {"lighting_mode": "dark_field"},
    {"angle_deg": 120},
    {"angle_deg": False},
    {"captured_monotonic": 9.999},
    {"captured_monotonic": 10.001},
    {"captured_monotonic": float("nan")},
    {"frame_id": True},
    {"frame_id": -1},
])
def test_frames_must_belong_to_current_ready_window(gate, metadata):
    controller, clock = gate
    ready(controller)
    with pytest.raises(ProtocolError):
        controller.authorize_frame(frame(controller, clock, **metadata))


def test_readiness_loss_starts_a_new_capture_window(gate):
    controller, clock = gate
    ready(controller)
    clock.value += 0.2
    controller.receive(controller.make_status(material_present=False))
    clock.value += 0.2
    controller.receive(controller.make_status())
    with pytest.raises(ProtocolError, match="timestamp outside"):
        controller.authorize_frame(frame(controller, clock, captured_monotonic=10.1))
    controller.authorize_frame(frame(controller, clock))


def test_off_ack_requires_zero_drive_and_no_fault(gate):
    controller, clock = gate
    ready(controller)
    controller.finish()
    with pytest.raises(ProtocolError, match="zero driver"):
        controller.receive(controller.make_status(driver_value=0.5))
    assert controller.state == "WAIT_OFF"
    with pytest.raises(ProtocolError, match="fault-free"):
        controller.receive(controller.make_status(fault="simulated_fault"))
    assert controller.state == "WAIT_OFF"
    controller.receive(controller.make_status())
    assert controller.state == "OFF"


def test_clock_rollback_cannot_authorize_capture(gate):
    controller, clock = gate
    ready(controller)
    clock.value -= 0.1
    with pytest.raises(ProtocolError, match="backwards"):
        controller.authorize_frame(frame(controller, clock))
    assert controller.state == "BLOCKED"


@pytest.mark.parametrize("raw", [
    "{bad-json}", "[]", "null", '{"seq": 1, "seq": 2}',
    '{"driver_value": NaN}', '{"driver_value": Infinity}',
    "{}\n{}", " " * 4097, b"\xff", "\ud800", {"field": float("nan")},
])
def test_json_boundary_rejects_malformed_duplicate_or_oversized_input(raw):
    with pytest.raises(ProtocolError):
        decode_message(raw)


def test_json_roundtrip_has_single_line_and_no_nan():
    encoded = encode_message({"message": "value\nwith\nnewlines", "seq": 0})
    assert encoded.count("\n") == 1
    assert decode_message(encoded) == json.loads(encoded)
    with pytest.raises(ProtocolError, match="4096"):
        encode_message({"value": "x" * 4096})


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_unknown_or_missing_schema_fields_fail_closed(gate, change):
    controller, clock = gate
    ready(controller)
    status = controller.make_status()
    if change == "missing":
        status.pop("reference_reading")
    else:
        status["rejection_enabled"] = True
    with pytest.raises(ProtocolError, match="schema fields"):
        controller.receive(status)
    assert controller.state == "BLOCKED"
