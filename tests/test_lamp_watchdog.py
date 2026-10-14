import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "lamp_watchdog", Path(__file__).resolve().parents[1] / "scripts" / "lamp_watchdog.py")
lamp_watchdog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lamp_watchdog)
decide = lamp_watchdog.decide


def test_healthy_service_feeds_heartbeat_and_arms_a_faulted_board():
    commands, timeout_sent, last_arm = decide(10.0, 9.9, "FAULT", float("-inf"), False, 50)
    assert commands == ["HB", "DUTY,50", "ARM"]
    assert timeout_sent is False and last_arm == 10.0


def test_rearm_attempts_are_spaced():
    commands, _, last_arm = decide(11.0, 10.9, "FAULT", 10.0, False, 50)
    assert commands == ["HB"] and last_arm == 10.0


def test_normal_board_only_gets_heartbeats():
    assert decide(10.0, 9.9, "NORMAL", float("-inf"), False, 50)[0] == ["HB"]


def test_unhealthy_service_sends_one_timeout_then_silence():
    commands, timeout_sent, _ = decide(10.0, 7.5, "NORMAL", 0.0, False, 50)
    assert commands == ["TIMEOUT"] and timeout_sent is True
    commands, timeout_sent, _ = decide(10.1, 7.5, "SUSPECT", 0.0, True, 50)
    assert commands == [] and timeout_sent is True


def test_state_reports_must_be_complete():
    parse = lamp_watchdog.parse_state
    assert parse(b"STATE,NORMAL,50,1234\r") == ["STATE", "NORMAL", "50", "1234"]
    assert parse(b"FAUSTATE,FAULT,0,2004") is None        # tail of a report cut off at port open
    assert parse(b"STATE,FAU") is None
    assert parse(b"ERR,ARM") is None


def test_recovery_clears_the_timeout_flag():
    commands, timeout_sent, _ = decide(20.0, 19.9, "FAULT", 0.0, True, 40)
    assert commands == ["HB", "DUTY,40", "ARM"] and timeout_sent is False
