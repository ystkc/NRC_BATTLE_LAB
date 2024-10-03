from pathlib import Path

import cv2

from collector.screen.realtime import BattleFeatureDetector


ROOT = Path(__file__).resolve().parents[1]


def _detector() -> BattleFeatureDetector:
    return BattleFeatureDetector(ROOT / "normal.jpg")


def test_reference_feature_signatures():
    detector = _detector()
    entrance = detector.detect(cv2.imread(str(ROOT / "entrance.jpg")))
    normal = detector.detect(cv2.imread(str(ROOT / "normal.jpg")))
    perform = detector.detect(cv2.imread(str(ROOT / "perform.jpg")))
    counter = detector.detect(cv2.imread(str(ROOT / "perform_counter.jpg")))
    speed = detector.detect(cv2.imread(str(ROOT / "speedcomp.jpg")))

    assert entrance.entrance
    assert normal.normal_icon
    assert perform.perform
    assert counter.perform_counter
    assert speed.speedcomp


def test_non_matching_reference_features_are_not_confused():
    detector = _detector()
    entrance = detector.detect(cv2.imread(str(ROOT / "entrance.jpg")))
    normal = detector.detect(cv2.imread(str(ROOT / "normal.jpg")))
    perform = detector.detect(cv2.imread(str(ROOT / "perform.jpg")))

    assert not entrance.normal_icon
    assert not normal.entrance
    assert not perform.speedcomp
