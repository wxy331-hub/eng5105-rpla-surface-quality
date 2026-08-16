import cv2

from src.week2_opencv_check import analyse_image, create_synthetic_filament


def test_synthetic_image_shape() -> None:
    image = create_synthetic_filament()
    assert image.shape == (360, 640, 3)


def test_analysis_returns_pass_and_annotation() -> None:
    image = create_synthetic_filament()
    annotated, result = analyse_image(image)

    assert annotated.shape == image.shape
    assert result["status"] == "PASS"
    assert result["opencv_version"] == cv2.__version__
    assert result["significant_contours"] >= 1

