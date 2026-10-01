"""最小 mitmproxy 原始流采集插件。

当前不假设游戏协议字段。它只负责保存请求/响应元数据和可解析 JSON；协议归一化留给
后续适配器，避免错误猜测导致原始证据丢失。

用法示例：
    mitmdump -s collector/mitmproxy_addon/collector_addon.py --set nrc_output=data/mitm/raw.jsonl
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from mitmproxy import http
except ImportError:  # 允许核心项目在未安装 mitmproxy 时导入本模块
    http = Any  # type: ignore


class BattleDataAddon:
    def __init__(self) -> None:
        self.output = Path(os.environ.get("NRC_MITM_OUTPUT", "data/mitm/raw.jsonl"))
        self.output.parent.mkdir(parents=True, exist_ok=True)

    def load(self, loader) -> None:
        loader.add_option(
            name="nrc_output",
            typespec=str,
            default=str(self.output),
            help="NRC 原始流 JSONL 输出路径",
        )

    def configure(self, updated) -> None:
        if "nrc_output" in updated:
            self.output = Path(updated["nrc_output"])
            self.output.parent.mkdir(parents=True, exist_ok=True)

    def response(self, flow: "http.HTTPFlow") -> None:
        self._write_flow(flow, "response")

    def request(self, flow: "http.HTTPFlow") -> None:
        self._write_flow(flow, "request")

    def _write_flow(self, flow, direction: str) -> None:
        message = flow.request if direction == "request" else flow.response
        if message is None:
            return
        body = bytes(message.raw_content or b"")
        parsed: Any = None
        content_type = message.headers.get("content-type", "")
        if "json" in content_type.lower():
            try:
                parsed = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
        record = {
            "captured_at": time.time(),
            "flow_id": flow.id,
            "direction": direction,
            "request": {
                "method": flow.request.method,
                "url": flow.request.pretty_url,
                "headers": dict(flow.request.headers),
            },
            "response": {
                "status_code": flow.response.status_code if flow.response else None,
                "headers": dict(flow.response.headers) if flow.response else {},
            },
            "content_type": content_type,
            "body_text": body.decode("utf-8", errors="replace")[:2_000_000],
            "json": parsed,
        }
        with self.output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


addons = [BattleDataAddon()]

