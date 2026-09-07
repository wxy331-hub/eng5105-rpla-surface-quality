"""Native synthetic geometry and pixel-scaled candidate settings."""

import hashlib

import cv2
import numpy as np
import pytest

from src.synthetic_profile import annotate_synthetic_candidates, synthetic_vision_profile
from src.week3.models import CameraState, FramePacket
from src.week3.sources import SyntheticCameraSource
from src.week3.vision import BaselineVisionProcessor


REFERENCE_HASHES = (
    "e1a9ed0335cdf724f9e758ba1e0a338c5a56fa046a08f181c132270f5a647062",
    "8fe13a2150f6a7c1b05611a957a7b9e5d12a342a62044daccab33c993f5ff5ab",
    "32b4eb29b4b7f0e1f8d47f891709a1d4a9b8bcf9ad6cfe8f115c216db237c976",
    "1b556d7d71df359ad40ba68facbd3bc96480df4bf42b99f11c91e0e2be1d2d4a",
)


@pytest.mark.parametrize("frame_id,expected_hash", enumerate(REFERENCE_HASHES))
def test_existing_reference_fixture_bytes_are_unchanged(frame_id, expected_hash):
    legacy = SyntheticCameraSource()._make_frame(frame_id)
    explicit = SyntheticCameraSource(reference_size_px=(640, 360))._make_frame(frame_id)
    assert hashlib.sha256(legacy.tobytes()).hexdigest() == expected_hash
    np.testing.assert_array_equal(explicit, legacy)


@pytest.fixture(scope="module")
def uhd_frames():
    source = SyntheticCameraSource(
        width_px=3840, height_px=2160, reference_size_px=(640, 360),
    )
    # Any attempt to upscale a reference raster would fail this check.
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cv2, "resize", lambda *args, **kwargs: pytest.fail("resized source raster"))
        source.connect()
        try:
            return list(source.frames(4))
        finally:
            source.disconnect()


def test_uhd_is_native_seeded_geometry_with_independent_target_pixel_noise(uhd_frames):
    clean = uhd_frames[3].image
    assert clean.shape == (2160, 3840, 3)
    assert clean.dtype == np.uint8
    # Reference left/right margin 24 and strand half-height 40 scale by six.
    assert clean[1080, 143, 0] > 200
    assert clean[1080, 144, 0] < 110
    assert clean[839, 1920, 0] > 200
    assert clean[840, 1920, 0] < 110
    assert clean[1320, 1920, 0] < 110
    assert clean[1321, 1920, 0] > 200
    blocks = clean[:60, :60, 0].reshape(10, 6, 10, 6).transpose(0, 2, 1, 3)
    # A nearest-neighbour upscale would have one value per six-pixel block.
    assert np.all(np.ptp(blocks, axis=(2, 3)) > 0)
    repeated = SyntheticCameraSource(
        width_px=3840, height_px=2160, reference_size_px=(640, 360),
    )._make_frame(3)
    np.testing.assert_array_equal(repeated, clean)


def test_profile_scales_lengths_areas_and_kernels_without_changing_intensity_rules():
    reference = synthetic_vision_profile(640, 360)
    uhd = synthetic_vision_profile(3840, 2160)
    assert uhd["roi_px"] == (168, 864, 3504, 432)
    for key in ("min_area_px", "score_area_divisor_px", "reject_area_px", "contamination_min_area_px"):
        assert uhd[key] == reference[key] * 36
    assert (uhd["blur_kernel_size"], uhd["morph_kernel_size"]) == (25, 13)
    processor = BaselineVisionProcessor(**uhd)
    defaults = BaselineVisionProcessor()
    assert processor.threshold == defaults.threshold
    assert processor.scratch_min_aspect == defaults.scratch_min_aspect
    assert processor.score_base == defaults.score_base
    assert processor.score_ceiling == defaults.score_ceiling


def test_candidates_remain_consistent_across_native_resolutions(uhd_frames):
    small = SyntheticCameraSource(reference_size_px=(640, 360))
    small_processor = BaselineVisionProcessor(**synthetic_vision_profile(640, 360))
    uhd_processor = BaselineVisionProcessor(**synthetic_vision_profile(3840, 2160))
    for packet in uhd_frames:
        reference_packet = FramePacket(
            source_name=packet.source_name, frame_id=packet.frame_id,
            captured_at_utc=packet.captured_at_utc, received_at_utc=packet.received_at_utc,
            camera_state=CameraState.HEALTHY, image=small._make_frame(packet.frame_id),
        )
        _, small_records = small_processor.process(reference_packet, "SYNTHETIC")
        _, large_records = uhd_processor.process(packet, "SYNTHETIC")
        assert len(small_records) == len(large_records) == (0 if packet.frame_id == 3 else 1)
        for reference, native in zip(small_records, large_records, strict=True):
            assert native.defect_type == reference.defect_type
            assert native.quality_grade == reference.quality_grade
            # Rasterisation and discrete contour area need not be identical.
            assert native.area_px / 36 == pytest.approx(reference.area_px, rel=0.22)
            assert native.confidence == pytest.approx(reference.confidence, abs=0.04)
            np.testing.assert_allclose(np.array(native.bbox_px) / 6, reference.bbox_px, atol=2)
            assert native.calibration_id is None
            assert native.size_mm is None
            assert native.position_mm is None


@pytest.mark.parametrize("frame_id,colour", [(0, (60, 162, 223)), (2, (60, 84, 194))])
def test_uhd_annotation_uses_current_records_scaled_strokes_and_preserves_raw(uhd_frames, frame_id, colour):
    packet = uhd_frames[frame_id]
    raw_before = packet.image.copy()
    _, records = BaselineVisionProcessor(**synthetic_vision_profile(3840, 2160)).process(packet, "SYNTHETIC")
    record_before = records[0].to_dict()
    display = annotate_synthetic_candidates(packet.image, records)
    np.testing.assert_array_equal(packet.image, raw_before)
    assert not np.shares_memory(display, packet.image)
    assert records[0].to_dict() == record_before
    x, y, width, _ = records[0].bbox_px
    middle_x = x + width // 2
    # At UHD the 12-pixel OpenCV stroke spans its centre plus six each side.
    np.testing.assert_array_equal(display[y - 6:y + 7, middle_x], np.tile(colour, (13, 1)))
    np.testing.assert_array_equal(display[y - 7, middle_x], raw_before[y - 7, middle_x])
    np.testing.assert_array_equal(display[y, x:x + width], np.tile(colour, (width, 1)))
    # The candidate's label is also rendered above its own recomputed box.
    assert np.count_nonzero(display[y - 120:y - 24] != raw_before[y - 120:y - 24]) > 100


def test_annotation_without_candidates_returns_an_independent_unchanged_image(uhd_frames):
    raw = uhd_frames[3].image
    display = annotate_synthetic_candidates(raw, [])
    assert not np.shares_memory(display, raw)
    np.testing.assert_array_equal(display, raw)


@pytest.mark.parametrize("width,height", [(0, 360), (640, -1), (640.0, 360), (True, 360), (800, 600)])
def test_invalid_or_distorted_target_sizes_are_rejected(width, height):
    with pytest.raises(ValueError):
        synthetic_vision_profile(width, height)
    with pytest.raises(ValueError):
        SyntheticCameraSource(width_px=width, height_px=height, reference_size_px=(640, 360))


@pytest.mark.parametrize("roi", [(0, 0, 0, 5), (-1, 0, 10, 10), (600, 300, 80, 80), (0, 0, 3.5, 10)])
def test_invalid_reference_roi_is_rejected(roi):
    with pytest.raises(ValueError):
        synthetic_vision_profile(3840, 2160, reference_roi_px=roi)
