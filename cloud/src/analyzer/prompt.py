import json

from .validate import ParsedEvent

SYSTEM_PROMPT = (
    "あなたは加速度センサーのイベント解析アシスタントです。"
    "与えられた特徴量から、デバイスの状態を分類し、深刻度と短い説明を日本語で返します。"
)


def build_user_message(event: ParsedEvent) -> str:
    payload = {
        "event_hint": event.event_hint,
        "features": event.features,
        "ts": event.ts,
    }
    return (
        "次の加速度イベントを解析してください。\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n\n"
        "必ず次のJSON形式のみで回答してください:\n"
        '{"label": "<normal|vibration|tilt|impact|freefall|transport>", '
        '"severity": "<low|medium|high>", '
        '"explanation": "<日本語の短い説明>"}'
    )
