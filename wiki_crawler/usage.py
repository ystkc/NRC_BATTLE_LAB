"""按单个精灵读取 Wiki 培养栏目公开提供的 PVP 统计。"""

from __future__ import annotations

import base64
import json
import math
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


CATEGORIES = {"skills": "skill", "natures": "nature", "bloodlines": "blood", "talents": "talent"}
WIKI_ORIGIN = "https://wiki.biligame.com"


def _request_bytes(url: str, payload: dict | None = None, referer: str = WIKI_ORIGIN) -> bytes:
    """发送一次 Wiki 请求，保留 HTTP 拒绝或限流错误。"""
    headers = {"User-Agent": "NRC-Battle-Lab/1.0", "Referer": referer}
    body = None
    if payload is not None:
        headers.update({"Content-Type": "application/json", "Origin": WIKI_ORIGIN})
        body = json.dumps(payload).encode("utf-8")
    with urlopen(Request(url, data=body, headers=headers), timeout=12) as response:
        return response.read()


def read_usage(spirit_name: str, source_url: str = "") -> dict[str, list[dict]]:
    """按详情页身份申请一次会话并解密 PVP 统计。"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    source_url = source_url or f"{WIKI_ORIGIN}/nrc/{quote(spirit_name, safe='')}"
    if urlsplit(source_url).netloc != "wiki.biligame.com" or not source_url.startswith(WIKI_ORIGIN + "/nrc/"):
        raise ValueError("培养统计需要 NRC Wiki 精灵详情页地址")
    source_url = quote(source_url, safe=":/?=&%")
    html = _request_bytes(source_url).decode("utf-8")
    root = BeautifulSoup(html, "html.parser").select_one("[data-pet-usage-page]")
    if root is None:
        raise ValueError("详情页缺少培养统计入口")
    endpoint = urljoin(source_url, root.get("data-pet-usage-api") or "/api/pet-usage/v2").rstrip("/")
    if endpoint not in {f"{WIKI_ORIGIN}/api/pet-usage/v2", "https://keys.p1.wiki/api/pet-usage/v2"}:
        raise ValueError("未知的 Wiki 培养统计接口")
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    key_text = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    session = json.loads(_request_bytes(endpoint + "/session", {"page": root["data-pet-usage-page"], "key": key_text}, source_url))
    ticket = session["ticket"]
    packet = _request_bytes(endpoint + "/read", {"ticket": ticket}, source_url)
    if len(packet) < 110 or packet[0] != 1:
        raise ValueError("培养统计响应格式异常")
    # 与 PetUsage.js 一致：ECDH → HKDF-SHA256 → AES-GCM，ticket 参与认证。
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), packet[1:66])
    shared = private.exchange(ec.ECDH(), peer)
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=packet[66:82], info=b"nrc-pet-usage/v2/read").derive(shared)
    data = json.loads(AESGCM(key).decrypt(packet[82:94], packet[94:], ticket.encode("utf-8")))
    if data.get("status") not in {"ok", "empty"} or not isinstance(data.get("teams"), dict):
        raise ValueError("培养统计未就绪或返回格式异常")
    if data["status"] == "empty":
        return {kind: [] for kind in CATEGORIES.values()}
    return parse_usage(data["teams"]["2"])


def parse_usage(team_data: dict) -> dict[str, list[dict]]:
    """解析接口提供的各项占比与完整排名。"""
    result = {}
    for category, kind in CATEGORIES.items():
        rows = []
        for position, item in enumerate(team_data[category], 1):
            name, percent = item.get("name"), item.get("percent")
            if percent is None:
                continue  # Wiki 用破折号显示没有占比的项目。
            if not isinstance(name, str) or not name or isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent):
                raise ValueError(f"培养统计 {category} 第 {position} 条缺少名称或有效百分比")
            rows.append({"item": name, "percentage": percent, "position": position})
        result[kind] = rows
    return result
