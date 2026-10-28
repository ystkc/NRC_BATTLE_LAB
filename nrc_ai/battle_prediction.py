"""Turn partial battle-log history into core setups and readable predictions."""


def _unavailable(*args, **kwargs):
    """旧战报补全预测已停用，等待明确目录与隐藏信息边界。"""
    raise NotImplementedError("AI 战报补全与预测尚未实现。")

build_round_setups = _unavailable
format_prediction_review = _unavailable
predict_round_setups = _unavailable
