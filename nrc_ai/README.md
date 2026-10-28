# AI 原型（尚未实现）

正式功能目前仅为 `nrc_platform` / `nrc_server` 双人对战。`nrc_ai` 的信念、搜索、自博弈与训练代码作为原型保留，未接入正式对战流程。

`python -m nrc_ai` 明确返回尚未实现；旧训练命令、战报自动补全预测和依赖全局目录的资质候选路径均已停用。

共享动作与运行协议位于 `nrc_core/contracts.py`。真正的战斗推进由 `nrc_core.runtime.BattleRuntime` 负责，上层必须显式注入 `CoreCatalog`，核心不再为 AI 自动查库。

后续开发需重新明确隐藏信息、目录注入与策略输入边界，不得将全知状态直接作为动作模型的可见输入。
