import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from collector.screen.entrance_detector import EntranceRegionDetector
from collector.screen.entrance_regions import REFERENCES, benchmark, score_regions
from collector.screen.region_geometry import Region


def synthetic_scene(offset_x=0, offset_y=0):
    image = np.full((760, 1100, 3), (190, 140, 35), dtype=np.uint8)
    for index in range(6):
        left, top = 120 + offset_x, 150 + index * 80 + offset_y
        color = (70, 180, 245) if index == 0 else (35, 38, 32)
        radius = 31
        cv2.rectangle(image, (left + radius, top), (left + 250 - radius, top + 62), color, -1)
        cv2.circle(image, (left + radius, top + radius), radius, color, -1)
        cv2.circle(image, (left + 250 - radius, top + radius), radius, color, -1)
        cv2.rectangle(image, (left + 110, top + 40), (left + 204, top + 55), (40, 160, 70), -1)
        cv2.circle(image, (left + 12, top + 2), 11, (35, 38, 32), -1)
        cv2.putText(image, "?", (left + 7, top + 7), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (245, 245, 245), 1)
    cv2.rectangle(image, (630 + offset_x, 650 + offset_y), (809 + offset_x, 700 + offset_y), (70, 180, 245), -1)
    return image


class EntranceDetectorTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        self.detector = EntranceRegionDetector()

    def test_blank_frames_return_no_boxes(self):
        for value in (0, 35, 255):
            with self.subTest(value=value):
                self.assertEqual(self.detector.detect(np.full((640, 960, 3), value, dtype=np.uint8)), [])

    def test_boxes_follow_translated_pixels(self):
        original = self.detector.detect(synthetic_scene())
        moved = self.detector.detect(synthetic_scene(57, 29))
        self.assertEqual(sum(region.name.endswith("_card") for region in original), 6)
        self.assertGreaterEqual(len(original), 12)
        self.assertEqual(len(original), len(moved))
        for first, second in zip(original, moved):
            with self.subTest(name=first.name):
                self.assertEqual(first.name, second.name)
                self.assertEqual((second.x - first.x, second.y - first.y), (57, 29))
                self.assertEqual((first.w, first.h), (second.w, second.h))

    def test_card_boxes_follow_resized_pixels(self):
        image = synthetic_scene()
        original = [region for region in self.detector.detect(image) if region.name.endswith("_card")]
        resized = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
        scaled = [region for region in self.detector.detect(resized) if region.name.endswith("_card")]
        self.assertEqual(len(original), 6)
        self.assertEqual(len(original), len(scaled))
        for first, second in zip(original, scaled):
            for expected, actual in zip(first.as_xywh(), second.as_xywh()):
                self.assertLessEqual(abs(expected * 2 - actual), 4)

    def test_evaluation_annotations_cannot_change_detection(self):
        image = synthetic_scene()
        expected = self.detector.detect(image)
        with patch("collector.screen.entrance_regions.REFERENCES", ()):
            with patch.object(Path, "read_text", side_effect=AssertionError("Detector tried to read annotations")):
                self.assertEqual(self.detector.detect(image), expected)

    def test_invalid_input_is_rejected(self):
        for image in (None, np.zeros((10, 10), dtype=np.uint8), np.zeros((0, 10, 3), dtype=np.uint8)):
            with self.assertRaises(ValueError):
                self.detector.detect(image)

    def test_real_frame_has_positive_conservative_score(self):
        image_path = Path(__file__).resolve().parents[2] / "entrance.jpg"
        if not image_path.is_file():
            self.skipTest("Local entrance.jpg is unavailable")
        image = cv2.imread(str(image_path))
        predictions, elapsed = benchmark(self.detector, image, repeats=5)
        result = score_regions(predictions, REFERENCES, sum(elapsed) / len(elapsed))
        self.assertEqual(len(predictions), 18)
        self.assertEqual(result["missed"], [])
        self.assertGreater(result["score"], 0)
        self.assertGreater(result["coverage_score"], 0)
        self.assertEqual(len(elapsed), 5)


class RegionScoringTests(unittest.TestCase):
    def test_exact_predictions_have_no_spatial_penalty(self):
        result = score_regions(REFERENCES)
        self.assertEqual(result["score"], 100000)
        self.assertEqual(result["coverage_score"], 100000)

    def test_disjoint_prediction_uses_fifteen_point_penalty(self):
        reference = Region("target", 0, 0, 10, 10, 2)
        result = score_regions([Region("bad", 20, 20, 10, 10)], [reference], average_ms=3)
        self.assertEqual(result["missed_penalty"], 200)
        self.assertEqual(result["extra_penalty"], 1500)
        self.assertEqual(result["time_penalty"], 30)
        self.assertEqual(result["score"], 98270)

    def test_excess_uses_ten_point_penalty(self):
        result = score_regions([Region("prediction", 0, 0, 12, 10)], [Region("target", 0, 0, 10, 10, 2)])
        self.assertEqual(result["extra_penalty"], 200)

    def test_partial_coverage_is_penalized_in_conservative_score(self):
        result = score_regions([Region("prediction", 0, 0, 5, 10)], [Region("target", 0, 0, 10, 10, 2)])
        self.assertEqual(result["score"], 100000)
        self.assertEqual(result["coverage_score"], 99900)

    def test_overlapping_references_do_not_double_count_covered_area(self):
        references = [Region("first", 0, 0, 10, 10, 2), Region("second", 5, 0, 10, 10, 3)]
        result = score_regions([Region("prediction", 0, 0, 15, 10)], references)
        self.assertEqual(result["extra_penalty"], 0)
        self.assertEqual(result["coverage_score"], 100000)

    def test_benchmark_rejects_nonpositive_repeat_count(self):
        with self.assertRaises(ValueError):
            benchmark(EntranceRegionDetector(), synthetic_scene(), repeats=0)


if __name__ == "__main__":
    unittest.main()
