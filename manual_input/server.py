from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nrc_core import BattleSimulator

from manual_input.catalog import Catalog
from manual_input.recorder import BattleRecorder


def _json_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


def _safe_file(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def _parse_json_error(error: Exception) -> JSONResponse:
    if isinstance(error, json.JSONDecodeError):
        return _json_error(f"{type(error).__name__}: {error}", 400)
    if isinstance(error, ValueError):
        return _json_error(str(error), 422)
    return _json_error(f"{type(error).__name__}: {error}", 400)


def create_app(
    *,
    catalog: Catalog | None = None,
    recorder: BattleRecorder | None = None,
    simulator: BattleSimulator | None = None,
    static_root: str | Path | None = None,
    asset_root: str | Path | None = None,
) -> FastAPI:
    project_root = Path(__file__).resolve().parents[1]
    resolved_static_root = Path(static_root) if static_root else project_root / "manual_input" / "static"
    resolved_asset_root = Path(asset_root) if asset_root else project_root / "data"
    app = FastAPI(title="NRC Battle Lab Manual Input")
    app.state.catalog = catalog
    app.state.recorder = recorder or BattleRecorder()
    app.state.simulator = simulator or BattleSimulator()

    @app.get("/api/catalog", response_model=None)
    def search_catalog(kind: str = Query(default="pokemon"), q: str = Query(default="")) -> list[dict[str, Any]] | JSONResponse:
        try:
            if app.state.catalog is None:
                app.state.catalog = Catalog()
            return app.state.catalog.search(kind, q)
        except Exception as error:
            return _json_error(f"目录数据不可用: {error}", 503)

    @app.get("/api/battles")
    def list_battles() -> list[dict[str, Any]]:
        return app.state.recorder.list_battles()

    @app.get("/api/battle", response_model=None)
    def load_battle(id: str = Query(default="")) -> dict[str, Any] | JSONResponse:
        try:
            return app.state.recorder.load(id)
        except FileNotFoundError:
            return _json_error("battle not found", 404)

    @app.post("/api/simulate")
    async def simulate(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            result = app.state.simulator.resolve_turn(payload)
            return JSONResponse(result.to_json())
        except Exception as error:
            return _parse_json_error(error)

    @app.post("/api/save-round")
    async def save_round(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            battle_id = str(payload.get("battle_id") or "manual-battle")
            document = app.state.recorder.save_round(
                battle_id,
                payload.get("request") or {},
                payload.get("observed_after"),
                str(payload.get("note") or ""),
            )
            return JSONResponse(document, status_code=201)
        except Exception as error:
            return _parse_json_error(error)

    @app.post("/api/new-battle", response_model=None)
    def new_battle() -> JSONResponse:
        try:
            return JSONResponse(app.state.recorder.create_battle(), status_code=201)
        except Exception as error:
            return _parse_json_error(error)

    @app.post("/api/save-initial")
    async def save_initial(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
            document = app.state.recorder.save_initial(
                str(payload.get("battle_id") or ""), payload.get("request") or {}
            )
            return JSONResponse(document, status_code=201)
        except Exception as error:
            return _parse_json_error(error)

    @app.get("/assets/{asset_path:path}", response_model=None)
    def serve_asset(asset_path: str) -> FileResponse | JSONResponse:
        candidate = _safe_file(resolved_asset_root, asset_path)
        if candidate is None:
            return _json_error("asset not found1", 404)
        return FileResponse(candidate)

    @app.get("/{request_path:path}", response_model=None)
    def serve_static(request_path: str) -> FileResponse | JSONResponse:
        candidate = _safe_file(resolved_static_root, request_path or "index.html")
        if candidate is None:
            return _json_error("not found", 404)
        return FileResponse(candidate)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Manual browser battle recorder")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"Manual input UI: http://{args.host}:{args.port}/")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
