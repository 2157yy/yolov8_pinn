#!/usr/bin/env python3
"""Tests for strawberry_maturity_bridge.py

Run with: python3 -m pytest test_maturity_bridge.py -v
Or:       python3 test_maturity_bridge.py
"""

from __future__ import annotations

import base64
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# Ensure the project root is on sys.path
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Module under test
from strawberry_maturity_bridge import (
    DEFAULT_MATURITY_NAMES,
    MATURITY_COLORS,
    draw_annotations,
    encode_annotated_image,
    run_maturity_inference,
    load_model,
)


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------


class TestDefaultMaturityNames:
    def test_three_classes(self):
        assert len(DEFAULT_MATURITY_NAMES) == 3

    def test_class_names(self):
        assert DEFAULT_MATURITY_NAMES[0] == "halfripe"
        assert DEFAULT_MATURITY_NAMES[1] == "ripe"
        assert DEFAULT_MATURITY_NAMES[2] == "unripe"


class TestMaturityColors:
    def test_all_classes_have_colors(self):
        for name in DEFAULT_MATURITY_NAMES.values():
            assert name in MATURITY_COLORS, f"Missing color for {name}"

    def test_colors_are_bgr_triples(self):
        for name, color in MATURITY_COLORS.items():
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)


class TestDrawAnnotations:
    def make_image(self, w=400, h=300):
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_no_detections_returns_copy(self):
        img = self.make_image()
        result = draw_annotations(img, [])
        assert result.shape == img.shape
        assert np.array_equal(result, img)

    def test_single_detection_draws_rectangle(self):
        img = self.make_image()
        detections = [{
            "class_name": "ripe",
            "confidence": 0.95,
            "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 150},
        }]
        result = draw_annotations(img, detections)
        # Pixels on the rectangle border should have been modified
        assert not np.array_equal(result[21, 11], img[21, 11])

    def test_multiple_detections(self):
        img = self.make_image()
        detections = [
            {"class_name": "ripe", "confidence": 0.9, "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 150}},
            {"class_name": "unripe", "confidence": 0.8, "bbox": {"x1": 200, "y1": 50, "x2": 300, "y2": 180}},
            {"class_name": "halfripe", "confidence": 0.7, "bbox": {"x1": 150, "y1": 100, "x2": 250, "y2": 200}},
        ]
        result = draw_annotations(img, detections)
        assert result.shape == img.shape

    def test_unknown_class_uses_white(self):
        img = self.make_image()
        detections = [{
            "class_name": "unknown_class",
            "confidence": 0.5,
            "bbox": {"x1": 10, "y1": 20, "x2": 100, "y2": 150},
        }]
        result = draw_annotations(img, detections)
        assert result.shape == img.shape


class TestEncodeAnnotatedImage:
    def test_returns_valid_base64_jpeg(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        b64 = encode_annotated_image(img)
        # Must be valid base64
        decoded = base64.b64decode(b64)
        assert len(decoded) > 0
        # Must be a valid JPEG
        img_decoded = cv2.imdecode(np.frombuffer(decoded, np.uint8), cv2.IMREAD_COLOR)
        assert img_decoded is not None
        assert img_decoded.shape == (100, 100, 3)


# ---------------------------------------------------------------------------
# Integration tests — run_maturity_inference with mock YOLO
# ---------------------------------------------------------------------------


class TestRunMaturityInference:
    def make_mock_result(self, boxes_data):
        """*boxes_data*: list of (cls_id, conf, x1, y1, x2, y2)"""
        mock_result = MagicMock()
        if boxes_data:
            mock_result.boxes = MagicMock()
            mock_result.boxes.xyxy = [
                MagicMock(tolist=lambda *, b=b: [b[2], b[3], b[4], b[5]])
                for b in boxes_data
            ]
            mock_result.boxes.cls = [
                MagicMock(item=lambda *, b=b: b[0]) for b in boxes_data
            ]
            mock_result.boxes.conf = [
                MagicMock(item=lambda *, b=b: b[1]) for b in boxes_data
            ]
        else:
            mock_result.boxes = None
        return mock_result

    def test_empty_detections(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = [self.make_mock_result([])]
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            result = run_maturity_inference(f.name, mock_model, 0.25)
        assert result["detections"] == []
        assert result["counts"] == {"halfripe": 0, "ripe": 0, "unripe": 0}

    def test_single_detection(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = [self.make_mock_result([
            (1, 0.95, 10, 20, 100, 150),  # ripe
        ])]
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            img = np.zeros((200, 200, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            result = run_maturity_inference(f.name, mock_model, 0.25)
        assert len(result["detections"]) == 1
        assert result["detections"][0]["class_name"] == "ripe"
        assert result["detections"][0]["confidence"] == 0.95
        assert result["detections"][0]["bbox"] == {"x1": 10.0, "y1": 20.0, "x2": 100.0, "y2": 150.0}
        assert result["counts"] == {"halfripe": 0, "ripe": 1, "unripe": 0}

    def test_multiple_classes(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = [self.make_mock_result([
            (0, 0.7, 10, 10, 50, 50),
            (0, 0.8, 60, 10, 100, 50),
            (1, 0.9, 10, 60, 50, 100),
            (2, 0.6, 60, 60, 100, 100),
            (2, 0.75, 110, 60, 150, 100),
        ])]
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            img = np.zeros((200, 200, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            result = run_maturity_inference(f.name, mock_model, 0.25)
        assert len(result["detections"]) == 5
        assert result["counts"] == {"halfripe": 2, "ripe": 1, "unripe": 2}

    def test_custom_maturity_names(self):
        custom_names = {0: "half", 1: "done", 2: "raw"}
        mock_model = MagicMock()
        mock_model.predict.return_value = [self.make_mock_result([
            (0, 0.9, 10, 10, 50, 50),
        ])]
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            result = run_maturity_inference(f.name, mock_model, 0.25, maturity_names=custom_names)
        assert result["detections"][0]["class_name"] == "half"
        assert "half" in result["counts"]

    def test_unknown_class_id_falls_back(self):
        mock_model = MagicMock()
        mock_model.predict.return_value = [self.make_mock_result([
            (99, 0.5, 10, 10, 50, 50),
        ])]
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            result = run_maturity_inference(f.name, mock_model, 0.25)
        assert result["detections"][0]["class_name"] == "class_99"


# ---------------------------------------------------------------------------
# Load model tests
# ---------------------------------------------------------------------------


class TestLoadModel:
    def test_model_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_model("/nonexistent/path/model.pt")

    @patch("strawberry_maturity_bridge.YOLO")
    def test_existing_model_loads(self, mock_yolo_cls):
        with tempfile.NamedTemporaryFile(suffix=".pt") as f:
            model = load_model(f.name)
        mock_yolo_cls.assert_called_once()
        assert model is not None


# ---------------------------------------------------------------------------
# End-to-end main() tests (stdin/stdout)
# ---------------------------------------------------------------------------


class TestMainFunction:
    def _import_main(self):
        from strawberry_maturity_bridge import main as _main
        return _main

    def test_empty_stdin(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        from strawberry_maturity_bridge import main
        exit_code = main()
        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert exit_code == 1
        assert result["success"] is False
        assert "Empty" in result["error"]

    def test_invalid_json(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
        from strawberry_maturity_bridge import main
        exit_code = main()
        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert exit_code == 1
        assert result["success"] is False

    def test_missing_image_path(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO('{"image_path": "/nonexistent/img.jpg"}'))
        from strawberry_maturity_bridge import main
        exit_code = main()
        captured = capsys.readouterr()
        result = json.loads(captured.out.strip())
        assert exit_code == 1
        assert result["success"] is False

    def test_missing_model_returns_error(self, monkeypatch, capsys):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            img = np.zeros((50, 50, 3), dtype=np.uint8)
            cv2.imwrite(f.name, img)
            payload = json.dumps({
                "image_path": f.name,
                "model_path": "/nonexistent/model.pt",
            })
            monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
            from strawberry_maturity_bridge import main
            exit_code = main()
            captured = capsys.readouterr()
            result = json.loads(captured.out.strip())
            assert exit_code == 1
            assert result["success"] is False

    def test_successful_inference_returns_annotated_image(self, monkeypatch, capsys):
        with tempfile.NamedTemporaryFile(suffix=".pt") as model_file, \
             tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            cv2.imwrite(image_file.name, img)

            payload = json.dumps({
                "image_path": image_file.name,
                "model_path": model_file.name,
                "conf_threshold": 0.25,
            })
            monkeypatch.setattr(sys, "stdin", io.StringIO(payload))

            mock_model = MagicMock()
            mock_result = MagicMock()
            mock_result.boxes = None
            mock_model.predict.return_value = [mock_result]

            with patch("strawberry_maturity_bridge.YOLO", return_value=mock_model):
                from strawberry_maturity_bridge import main
                exit_code = main()

            captured = capsys.readouterr()
            result = json.loads(captured.out.strip())
            assert exit_code == 0
            assert result["success"] is True
            assert "data" in result
            assert "annotated_image_base64" in result["data"]
            assert "detections" in result["data"]
            assert result["data"]["counts"] == {"halfripe": 0, "ripe": 0, "unripe": 0}


# ---------------------------------------------------------------------------
# CLI runner (when invoked directly without pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(Path(__file__).resolve().parent),
    )
    raise SystemExit(result.returncode)
