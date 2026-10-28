"""浏览器资源路径与图标装饰。"""
from __future__ import annotations
import copy
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


def _base_name(name: str) -> str:
    """取资源匹配使用的精灵基础名称。"""
    return re.split(r"[（(]", str(name), maxsplit=1)[0].strip()


@lru_cache(maxsize=8)
def _asset_files(root: Path, directory: str) -> tuple[Path, ...]:
    """缓存静态资源目录内容。"""
    folder = root / directory
    if not folder.exists():
        return ()
    return tuple(path for path in folder.iterdir() if path.is_file())

@lru_cache(maxsize=16384)
def _asset(root: Path, directory: str, name: str, *, portrait: bool = False) -> str | None:
    """按原名称匹配资源文件，不参与资料解析。"""
    tokens = [part for part in re.split(r'[（）()]', name) if part]
    candidates = [path for path in _asset_files(root, directory) if all(token in path.stem for token in tokens)]
    if not candidates:
        candidates = [path for path in _asset_files(root, directory) if _base_name(name) in path.stem]
    if portrait:
        candidates = [path for path in candidates if "portrait" in path.stem] or candidates
    else:
        candidates = [path for path in candidates if "portrait" not in path.stem] or candidates
    if not candidates:
        return None
    candidates.sort(key=lambda path: ("_main_" not in path.stem, len(path.name)))
    return "/assets/" + directory + "/" + candidates[0].name

def _asset_exact(root: Path, directory: str, filename: str) -> str | None:
    """返回存在的精确资源路径。"""
    path = root / directory / filename
    return f"/assets/{directory}/{filename}" if path.is_file() else None


def decorate_response(value: Any, data_root: Path) -> Any:
    """只补充静态资源信息，不修改对局规则与可见性。"""
    result = copy.deepcopy(value)
    def decorate(item: Any) -> None:
        """递归装饰响应中的显示条目。"""
        if isinstance(item, list):
            for child in item:
                decorate(child)
        elif isinstance(item, dict):
            for child in list(item.values()):
                decorate(child)
            # 观测层可能用 species/display_name 表示精灵名称。
            name = str(item.get("name") or item.get("species") or item.get("display_name") or "")
            if name and "name" not in item:
                item["name"] = name
            creature = any(key in item for key in ("types", "max_hp", "known", "skills", "bloodline_attributes"))
            skill = any(key in item for key in ("energy_cost", "power", "skill_slot"))
            if name and creature:
                item.setdefault("portrait", _asset(data_root, "spirit_icons", name, portrait=True))
                item.setdefault("art", _asset(data_root, "spirit_icons", name))
            if name and skill:
                item.setdefault("icon", _asset(data_root, "skill_icons", name))
            element = str(item.get("element") or "")
            if element:
                item["type_icon"] = _asset(data_root, "dept_icons", element)
            multiplier = item.get("type_effectiveness")
            if "type_effectiveness" in item:
                relation = '无' if multiplier is None else '双重克制' if float(multiplier) > 2 else '克制' if float(multiplier) > 1 else '双重抵抗' if 0 < float(multiplier) < 0.5 else '抵抗' if 0 < float(multiplier) < 1 else '平衡'
                item["effect_icon"] = _asset(data_root, "icon_dept_relation", relation)
    decorate(result)
    if isinstance(result, dict) and result.get("bloodline_attributes") is not None:
        bloodline = next(iter(result.get("bloodline_attributes") or []), "")
        result["bloodline_icon"] = _asset(data_root, "icon_blood", bloodline) if bloodline else None
        result["stat_icons"] = {key: _asset_exact(data_root, "icon_aptitudes", filename) for key, filename in {'hp': '生命.png', 'atk': '攻击.png', 'def': '物防.png', 'spatk': '魔攻.png', 'spdef': '魔防.png', 'speed': '速度.png'}.items()}
    return result

