"""HTTP 请求、身份认证与资源入口。"""
from __future__ import annotations
import argparse
import secrets
import uuid
from pathlib import Path
from typing import Any, Mapping
import mimetypes
mimetypes.add_type("application/javascript", ".js")
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from nrc_platform.platform import PlatformError
from nrc_platform.rooms import RoomService
from nrc_server.presentation import decorate_response

ROOT = Path(__file__).resolve().parents[1]

def _error_response(error: Exception) -> JSONResponse:
    """把平台错误映射为 HTTP 响应。"""
    if isinstance(error, PlatformError):
        status = {"not_found": 404, "battle_not_found": 404, "stale_decision": 409,
                  "already_submitted": 409, "invalid_phase": 409}.get(error.code, 422)
        return JSONResponse(error.to_dict(), status_code=status)
    if isinstance(error, (ValueError, TypeError)):
        message = str(error)
        status = 401 if message == "player token is required" else 403 if "not a member" in message else 404 if "not found" in message else 422
        return JSONResponse({"error": message}, status_code=status)
    return JSONResponse({"error": f"{type(error).__name__}: {error}"}, status_code=500)

def _identity(app: FastAPI, request: Request, *, create: bool = False) -> str:
    """将浏览器令牌解析为稳定身份，首次入场时签发令牌。"""
    token = request.headers.get("X-Player-Token", "")
    if token in app.state.sessions:
        return app.state.sessions[token]
    if not create:
        raise ValueError("player token is required")
    identity = uuid.uuid4().hex
    app.state.sessions[secrets.token_urlsafe(24)] = identity
    return identity


def _token_for(app: FastAPI, identity: str) -> str:
    """返回稳定身份已绑定的令牌。"""
    return next(token for token, player in app.state.sessions.items() if player == identity)


async def _payload(request: Request) -> Mapping[str, Any]:
    """验证 JSON 顶层为对象，避免无效请求进入平台。"""
    value = await request.json()
    if not isinstance(value, Mapping):
        raise ValueError("JSON payload must be an object")
    return value


def create_app() -> FastAPI:
    """装配 HTTP 路由、身份认证与资源服务。"""
    app = FastAPI(title="NRC Battle Server")
    app.state.rooms = RoomService()
    app.state.sessions: dict[str, str] = {}
    static_root = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_root), name="static")
    app.mount("/assets", StaticFiles(directory=ROOT / "data"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        """提供浏览器页面。"""
        return FileResponse(static_root / "index.html")

    @app.get('/api/catalog/index')
    def catalog_index() -> Any:
        """返回完整精灵与技能检索索引。"""
        try:
            result = app.state.rooms.catalog_index()
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/catalog')
    def catalog(kind: str = 'pokemon', q: str = '') -> Any:
        """按名称与拼音筛选检索数据。"""
        try:
            result = app.state.rooms.catalog(kind, q)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/pokemon/{name}')
    def pokemon_detail(name: str) -> Any:
        """返回指定精灵的基础展示数据和培养选项。"""
        try:
            result = app.state.rooms.pokemon_detail(name)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.post('/api/pokemon/preview')
    async def pokemon_preview(request: Request) -> Any:
        """根据用户配置生成精灵面板预览。"""
        try:
            payload = await _payload(request)
            result = await run_in_threadpool(app.state.rooms.pokemon_preview, payload)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.post('/api/battles')
    async def create_battle(request: Request) -> Any:
        """为当前身份创建双人房间。"""
        try:
            identity = _identity(app, request, create=True)
            payload = await _payload(request)
            result = app.state.rooms.create_battle(identity, payload)
            result['player_token'] = _token_for(app, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.post('/api/battles/{battle_id}/join')
    async def join_battle(battle_id: str, request: Request) -> Any:
        """加入空闲席位或恢复当前身份席位。"""
        try:
            identity = _identity(app, request, create=True)
            result = app.state.rooms.join_battle(battle_id, identity)
            result['player_token'] = _token_for(app, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}')
    def battle_summary(battle_id: str, request: Request) -> Any:
        """返回当前玩家可见的房间摘要。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.battle_summary(battle_id, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/opponent-roster')
    def opponent_roster(battle_id: str, request: Request) -> Any:
        """返回平台已遮蔽的对手阵容。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.opponent_roster(battle_id, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.post('/api/battles/{battle_id}/rosters')
    async def set_rosters(battle_id: str, request: Request) -> Any:
        """提交本人阵容并在双方确认后原子初始化。"""
        try:
            identity = _identity(app, request)
            payload = await _payload(request)
            result = await run_in_threadpool(app.state.rooms.set_rosters, battle_id, identity, payload)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/display')
    def display(battle_id: str, request: Request) -> Any:
        """返回本人技能显示值。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.display(battle_id, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/matchups')
    def matchups(battle_id: str, request: Request) -> Any:
        """返回当前玩家可见的属性关系。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.matchups(battle_id, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/actions')
    def actions(battle_id: str, request: Request) -> Any:
        """返回当前玩家的合法行动。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.actions(battle_id, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/state')
    def public_state(battle_id: str, request: Request) -> Any:
        """返回平台生成的玩家视角观测。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.public_state(battle_id, identity)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/operation')
    def operation(battle_id: str, request: Request, since: int = -1) -> Any:
        """返回双方行动提交进度。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.operation(battle_id, identity, since)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.get('/api/battles/{battle_id}/events')
    def battle_events(battle_id: str, request: Request, since: int = 0) -> Any:
        """按玩家视角与游标返回公开战报。"""
        try:
            identity = _identity(app, request)
            result = app.state.rooms.battle_events(battle_id, identity, since)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    @app.post('/api/battles/{battle_id}/selection')
    async def select_action(battle_id: str, request: Request) -> Any:
        """幂等提交本人行动并追加展示事件。"""
        try:
            identity = _identity(app, request)
            payload = await _payload(request)
            result = app.state.rooms.select_action(battle_id, identity, payload)
            return decorate_response(result, ROOT / "data")
        except Exception as error:
            return _error_response(error)

    return app


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the NRC battle UI")
    parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("nrc_server.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
