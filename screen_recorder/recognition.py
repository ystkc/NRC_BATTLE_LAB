"""校正截图区域并复用 RapidOCR 的检测与识别模型。"""

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from math import cos, radians, sin
from pathlib import Path
from time import perf_counter
from typing import Callable, Iterator

import cv2
import numpy as np
from rapidocr import ModelType, RapidOCR

from .program import OCRModels, Region


Polygon = tuple[tuple[float, float], ...]
PADDING_X = 8
PADDING_Y = 16


@dataclass(frozen=True)
class TextLine:
    """保存一行文字、置信度和原截图上的轮廓。"""

    text: str
    score: float
    box: Polygon | None = None


@dataclass(frozen=True)
class ModelFile:
    """为本地模型或字典文件记录可比较的版本。"""

    path: Path
    size: int
    modified_ns: int


def _model_file(path: str | None, label: str, *, onnx: bool = False) -> ModelFile | None:
    """解析本地路径并获取文件版本。"""
    if path is None:
        return None
    try:
        file = Path(path).expanduser().resolve()
        if not file.is_file():
            raise FileNotFoundError(path)
        info = file.stat()
    except (OSError, ValueError) as exc:
        raise ValueError(f"找不到{label}：{path}") from exc
    if onnx and file.suffix.lower() != ".onnx":
        raise ValueError(f"{label}需要使用 .onnx 文件：{path}")
    return ModelFile(file, info.st_size, info.st_mtime_ns)


def _crop_matrix(region: Region) -> np.ndarray:
    """将校正后的像素中心映射到原图的像素中心。"""
    angle = radians(region.angle)
    cosine, sine = cos(angle), sin(angle)
    dx, dy = (region.width - 1) / 2, (region.height - 1) / 2
    # 画布用像素边缘坐标，OpenCV 用像素中心坐标。
    x, y = region.x - 0.5, region.y - 0.5
    return np.array([
        [cosine, -sine, x - cosine * dx + sine * dy],
        [sine, cosine, y - sine * dx - cosine * dy],
    ])


def upright_crop(image: np.ndarray, region: Region) -> np.ndarray:
    """按区域的宽高截取像素，将顺时针倾角校正到水平。"""
    return cv2.warpAffine(
        image, _crop_matrix(region), (region.width, region.height),
        flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _screen_polygon(region: Region, box: np.ndarray | None, scale: float) -> Polygon:
    """撤销留白和缩放，再将文字轮廓转回截图坐标。"""
    right, bottom = region.width - 0.5, region.height - 0.5
    if box is None:
        points = np.array([[-0.5, -0.5], [right, -0.5], [right, bottom], [-0.5, bottom]])
    else:
        points = (box - (PADDING_X, PADDING_Y) + 0.5) / scale - 0.5
        points = np.clip(points, -0.5, (right, bottom))
    screen = cv2.transform(points[None, ...], _crop_matrix(region))[0] + 0.5
    return tuple((float(x), float(y)) for x, y in screen)


def _scale_crop(crop: np.ndarray) -> tuple[np.ndarray, float]:
    """放大小选区并保留缩放比例。"""
    scale = max(1, min(3, 48 / min(crop.shape[:2])))
    if scale > 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return crop, scale


def _text_line(
    region: Region, text: str, score: float, box: np.ndarray | None = None, scale: float = 1,
) -> TextLine | None:
    """按选区的置信度保留非空文字，并计算截图上的轮廓。"""
    text = text.strip()
    if text and score >= region.confidence:
        return TextLine(text, float(score), _screen_polygon(region, box, scale))
    return None


@contextmanager
def _limit_characters(model, characters: str) -> Iterator[None]:
    """在本次识别中限制 CTC 候选，同时保留原始置信度。"""
    if not characters:
        yield
        return
    decoder = model.postprocess_op
    missing = set(characters).difference(decoder.dict)
    if missing:
        raise ValueError(f"当前 OCR 模型不支持这些字符：{''.join(sorted(missing))}")
    indices = np.array(sorted({0, *(decoder.dict[char] for char in characters)}))

    def decode(preds: np.ndarray, return_word_box: bool, **kwargs):
        """只在允许字符与 CTC 空白之间选择概率最高的候选。"""
        allowed = preds[..., indices]
        best = allowed.argmax(axis=-1)
        scores = np.take_along_axis(allowed, best[..., None], axis=-1)[..., 0]
        return decoder.decode(indices[best], scores, return_word_box, remove_duplicate=True, **kwargs)

    model.postprocess_op = decode
    try:
        yield
    finally:
        model.postprocess_op = decoder


class Recognizer:
    """在录制任务之间复用 RapidOCR 模型和 ONNX 会话。"""

    def __init__(self) -> None:
        """推迟模型初始化，便于先在 Web 界面配置区域。"""
        self._engine = None
        self._selection = None
        self._detectors = OrderedDict()
        self._recognizers = OrderedDict()

    def prepare(self, models: OCRModels) -> None:
        """加载所选模型，复用缓存中相同的检测和识别阶段。"""
        detection = (
            _model_file(models.detection_path, "检测模型", onnx=True)
            if models.detection == "local" else None
        )
        recognition = (
            _model_file(models.recognition_path, "识别模型", onnx=True)
            if models.recognition == "local" else None
        )
        keys = _model_file(models.recognition_keys_path, "识别字符字典") if recognition else None
        detection_key = (models.detection, detection)
        recognition_key = (models.recognition, recognition, keys)
        selection = (detection_key, recognition_key)
        if selection == self._selection:
            return

        params = {
            "Global.use_cls": False,
            "Global.text_score": 0.0,
            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "Det.model_type": ModelType.SMALL if detection else ModelType(models.detection),
            "Rec.model_type": ModelType.SMALL if recognition else ModelType(models.recognition),
        }
        if detection:
            params["Det.model_path"] = str(detection.path)
        if recognition:
            params["Rec.model_path"] = str(recognition.path)
        if keys:
            params["Rec.rec_keys_path"] = str(keys.path)

        engine = RapidOCR(params=params)
        # 固定版本的 RapidOCR 在两个加载方法中分别创建 ONNX 会话。
        engine.text_det = self._cached(self._detectors, detection_key, engine._load_det_model)
        engine.text_rec = self._cached(self._recognizers, recognition_key, engine._load_rec_model)
        self._engine, self._selection = engine, selection

    @staticmethod
    def _cached(cache: OrderedDict, key: tuple, load: Callable):
        """保留每种处理阶段最近用过的四个模型。"""
        if key not in cache:
            cache[key] = load()
            if len(cache) > 4:
                cache.popitem(last=False)
        cache.move_to_end(key)
        return cache[key]

    def read(self, image: np.ndarray, region: Region) -> list[TextLine]:
        """从原截图裁剪、校正并识别区域。"""
        return self.read_crop(upright_crop(image, region), region)

    def read_crop(self, crop: np.ndarray, region: Region) -> list[TextLine]:
        """识别已校正的区域，应用置信度下限并返回截图坐标。"""
        if self._engine is None:
            self.prepare(OCRModels())
        crop, scale = _scale_crop(crop)
        if region.detect:
            # 给贴边文字留出检测空间，填充色取自选区自身的边缘。
            edges = np.concatenate((crop[0], crop[-1], crop[:, 0], crop[:, -1]))
            background = tuple(float(value) for value in np.median(edges, axis=0))
            crop = cv2.copyMakeBorder(
                crop, PADDING_Y, PADDING_Y, PADDING_X, PADDING_X, cv2.BORDER_CONSTANT, value=background,
            )
        with _limit_characters(self._engine.text_rec, region.allowed_chars):
            result = self._engine(crop, use_det=region.detect)
        boxes = getattr(result, "boxes", None)
        texts = getattr(result, "txts", None) or ()
        scores = getattr(result, "scores", None) or ()
        lines = []
        for index, (text, score) in enumerate(zip(texts, scores)):
            box = boxes[index] if boxes is not None else None
            line = _text_line(region, text, score, box, scale)
            if line is not None:
                lines.append(line)
        return lines

    def read_direct(
        self, crops: list[tuple[Region, np.ndarray]], check_stop: Callable[[], None],
    ) -> Iterator[list[tuple[str, list[TextLine], float]]]:
        """逐批返回关闭检测的选区结果和分摊耗时。"""
        if not crops:
            return
        if self._engine is None:
            self.prepare(OCRModels())
        engine = self._engine
        model = engine.text_rec
        # ONNX 输入的第一维决定模型能否接收动态批大小。
        batch_dimension = model.session.session.get_inputs()[0].shape[0]
        batch_size = 1 if isinstance(batch_dimension, int) else model.rec_batch_num
        _, model_height, model_width = model.rec_image_shape
        groups: dict[tuple[int, str], list[tuple[Region, np.ndarray, float]]] = {}
        for region, crop in crops:
            check_stop()
            started = perf_counter()
            crop, _ = _scale_crop(crop)
            crop, _ = engine.preprocess_img(engine.load_img(crop))
            height, width = crop.shape[:2]
            # 按单框推理时的宽度分组，避免宽框拉长同批小框的输入。
            input_width = int(model_height * max(model_width / model_height, width / height))
            characters = "".join(sorted(set(region.allowed_chars)))
            groups.setdefault((input_width, characters), []).append((region, crop, perf_counter() - started))

        for (_, characters), group in groups.items():
            for offset in range(0, len(group), batch_size):
                check_stop()
                batch = group[offset:offset + batch_size]
                started = perf_counter()
                with _limit_characters(model, characters):
                    result = engine.recognize_txt([crop for _, crop, _ in batch])
                shared = (perf_counter() - started) / len(batch)
                readings = []
                for (region, _, preprocessing), text, score in zip(batch, result.txts, result.scores):
                    started = perf_counter()
                    line = _text_line(region, text, score)
                    elapsed = preprocessing + shared + (perf_counter() - started)
                    readings.append((region.name, [line] if line is not None else [], elapsed))
                yield readings
