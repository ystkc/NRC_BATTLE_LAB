# mitmproxy 原始数据采集

当前插件只保存原始请求/响应，不假设游戏接口字段。这样可以先完整保留证据，待确认协议后再增加归一化适配器。

```bash
pip install -e ".[collector]"
mitmdump -s collector/mitmproxy_addon/collector_addon.py \
  --set nrc_output=data/mitm/raw.jsonl
```

输出格式为 JSONL，每行一个请求或响应事件，包含 URL、headers、状态码、文本和可解析 JSON。

