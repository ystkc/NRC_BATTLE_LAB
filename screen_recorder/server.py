"""提供截图、配置和后台录制任务的 Web 接口。"""

import re
from base64 import b64encode
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
import numpy as np
import yaml
import mimetypes
mimetypes.add_type("application/javascript", ".js")
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .desktop import CaptureError, Desktop
from .program import CaptureSource, Monitor, Program, Settings, Window
from .recognition import Recognizer
from .runner import Recorder, RoundPreview, RunBusy, dump_yaml


ROOT = Path(__file__).resolve().parent


class StartRequest(Settings):
    """携带待运行配置和试跑选项。"""

    program: Program
    trial: bool = False


class ImportRequest(Settings):
    """携带用户选择的 YAML 配置文件内容。"""

    yaml: str


def _preview_jpeg(preview: RoundPreview) -> str | None:
    """将本轮文字轮廓画到截图副本上并编码。"""
    image, boxes = preview
    if boxes:
        image = image.copy()
        # 轮廓使用画布坐标，换算为 OpenCV 的像素中心并保留小数位置。
        outlines = np.rint((np.asarray(boxes) - 0.5) * 16).astype(np.int32)
        thickness = max(1, round(max(image.shape[:2]) / 700))
        cv2.polylines(image, outlines, True, (22, 35, 29), thickness + 2, cv2.LINE_AA, shift=4)
        cv2.polylines(image, outlines, True, (225, 255, 90), thickness, cv2.LINE_AA, shift=4)
    ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return b64encode(jpeg).decode("ascii") if ok else None


def create_app(recorder: Recorder | None = None) -> FastAPI:
    """创建同一进程内控制桌面和 OCR 的 Web 服务。"""
    if recorder is None:
        recorder = Recorder(Desktop(), Recognizer(), ROOT / "recordings")

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """在 Web 服务退出时结束桌面任务。"""
        try:
            yield
        finally:
            thread = recorder.stop()
            if thread is not None:
                thread.join(timeout=3)

    app = FastAPI(title="屏幕 OCR", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        """只允许同源网页提交执行请求。"""
        if request.method == "POST":
            origin = request.headers.get("origin")
            media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if origin and origin != str(request.base_url).rstrip("/"):
                return JSONResponse({"detail": "请从本机 OCR 界面提交操作"}, status_code=403)
            if media_type != "application/json":
                return JSONResponse({"detail": "请求需要使用 JSON"}, status_code=415)
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        """显示工作台。"""
        return FileResponse(ROOT / "static" / "index.html")

    @app.get("/api/monitors")
    def monitors() -> list[Monitor]:
        """列出可用显示器。"""
        return recorder.desktop.monitors()

    @app.get("/api/windows")
    def windows() -> list[Window]:
        """列出可选的 Windows 应用窗口。"""
        return recorder.desktop.windows()

    @app.post("/api/screenshot")
    def screenshot(source: CaptureSource) -> Response:
        """为编辑器返回原始尺寸的 PNG 截图。"""
        try:
            image = recorder.preview(source)
        except RunBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        except CaptureError as exc:
            raise HTTPException(503, str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc
        ok, png = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 2])
        if not ok:
            raise HTTPException(500, "无法编码截图")
        return Response(png.tobytes(), media_type="image/png")

    @app.post("/api/start")
    def start(request: StartRequest) -> dict:
        """启动连续运行或单轮试跑。"""
        try:
            recorder.start(request.program, trial=request.trial)
        except RunBusy as exc:
            raise HTTPException(409, str(exc)) from exc
        except CaptureError as exc:
            raise HTTPException(503, str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(400, str(exc)) from exc
        return recorder.status()

    @app.post("/api/stop")
    def stop() -> dict:
        """停止周期识别及后续触发动作。"""
        recorder.stop()
        return recorder.status()

    @app.get("/api/status")
    def status(after_preview: str | None = None) -> dict:
        """返回最近一轮结果，并按需附上同一轮的画面。"""
        current, preview = recorder.snapshot()
        key = f"{current['recording']}/{current['rounds']}"
        if after_preview is not None and after_preview != key and preview is not None:
            current["preview_jpeg"] = _preview_jpeg(preview)
        return current

    @app.post("/api/config/import")
    def import_config(request: ImportRequest) -> Program:
        """解析用户编写或导出的 YAML 配置。"""
        try:
            return Program.model_validate(yaml.safe_load(request.yaml))
        except yaml.YAMLError as exc:
            raise HTTPException(422, f"YAML 格式错误：{exc}") from exc
        except ValidationError as exc:
            detail = exc.errors(include_input=False, include_url=False, include_context=False)
            raise HTTPException(422, detail) from exc

    @app.post("/api/config/export")
    def export_config(program: Program) -> Response:
        """把当前配置序列化为可再次导入的 YAML。"""
        exclude = {"monitor"} if program.window is not None else {"window"}
        return Response(dump_yaml(program.model_dump(exclude=exclude)), media_type="application/yaml")

    @app.get("/api/recordings/{filename}")
    def download_recording(filename: str) -> FileResponse:
        """下载指定任务已写入的全部轮次。"""
        path = recorder.directory / filename
        if not re.fullmatch(r"\d{8}-\d{6}-\d{6}\.yaml", filename) or not path.is_file():
            raise HTTPException(404, "找不到录制文件")
        return FileResponse(path, filename=filename, media_type="application/yaml")

    return app


app = create_app()
