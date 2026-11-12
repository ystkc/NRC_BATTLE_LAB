# T00 跨模块与运行约定问题

## T00-I01 · P2 · 核心必需的 NumPy 未列入基础或 dev 依赖

- 主责：T00（依赖清单）；协同：T03（核心数值）、T02（目录入口）。依据：AGENTS.md 的 `pip install -e ".[dev]"` 运行命令及核心必须可导入的接口约定。
- 代码：`pyproject.toml:12-16,33-35` 只有screen/training附加项声明NumPy；`nrc_core/catalog.py:12`、`constant.py` 直接导入NumPy，平台目录导入核心时也必需。
- 最小输入与步骤：`dependency_probe.py` 子进程仅模拟NumPy缺失，其余当前环境不变，`import nrc_platform.catalog`。
- 预期：安装声明的基础/dev依赖足以导入并运行核心。实际：阻断NumPy后 `ModuleNotFoundError`，而基础/dev声明均不含NumPy。
- 影响：干净环境依照文档只安装dev时可能启动/测试失败；当前机器已有NumPy所以19测试通过，不能据此证明依赖完整。未实际卸载软件，也不声称当前环境损坏。
- 证据：[dependency_probe.py](dependency_probe.py)、[dependency_output.json](dependency_output.json)。不涉及修复规则。
