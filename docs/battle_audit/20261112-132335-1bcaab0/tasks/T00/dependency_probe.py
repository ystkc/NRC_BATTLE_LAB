"""记录运行依赖，并隔离复现必需依赖未声明的导入失败。"""

import importlib.abc
import importlib.metadata
import json
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]


def main():
    """仅阻断numpy导入，不改安装环境或依赖文件。"""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    command = """import importlib.abc,sys
class MissingNumpy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'numpy' or fullname.startswith('numpy.'):
            raise ModuleNotFoundError("No module named 'numpy' (isolated audit probe)")
sys.meta_path.insert(0, MissingNumpy())
import nrc_platform.catalog
"""
    result = subprocess.run([sys.executable, "-c", command], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    packages = {}
    for name in ("numpy", "pytest", "fastapi", "uvicorn", "pypinyin", "beautifulsoup4", "PyYAML"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    output = {"python": sys.version, "dependencies": project["dependencies"], "dev_dependencies": project["optional-dependencies"]["dev"], "installed_versions": packages, "numpy_blocked_import": {"returncode": result.returncode, "stderr": result.stderr}, "scope": "simulated environment where only numpy is absent; no packages installed/uninstalled"}
    (HERE / "dependency_output.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"numpy_required_by_core": result.returncode != 0 and "numpy" in result.stderr, "declared_base_or_dev": any(name.startswith("numpy") for name in project["dependencies"] + project["optional-dependencies"]["dev"])}))


if __name__ == "__main__":
    main()
