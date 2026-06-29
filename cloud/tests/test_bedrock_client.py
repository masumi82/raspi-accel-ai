from analyzer.validate import ParsedEvent
from analyzer.analysis import Analysis
from analyzer.bedrock_client import analyze


class FakeBedrock:
    def __init__(self, text):
        self._text = text
        self.last_kwargs = None

    def converse(self, **kwargs):
        self.last_kwargs = kwargs
        return {"output": {"message": {"content": [{"text": self._text}]}}}


def _event():
    return ParsedEvent(
        device_id="raspi-01",
        ts="2026-06-29T12:34:56.789Z",
        event_hint="impact",
        features={"mag_peak": 3.21},
    )


def test_analyze_returns_analysis():
    client = FakeBedrock(
        '{"label": "impact", "severity": "high", "explanation": "衝撃検知"}'
    )
    result = analyze(client, "model-x", _event())
    assert result == Analysis(label="impact", severity="high", explanation="衝撃検知")


def test_analyze_passes_model_id_and_system_prompt():
    client = FakeBedrock(
        '{"label": "normal", "severity": "low", "explanation": "正常"}'
    )
    analyze(client, "model-x", _event())
    assert client.last_kwargs["modelId"] == "model-x"
    assert client.last_kwargs["system"][0]["text"]
    assert client.last_kwargs["messages"][0]["role"] == "user"
