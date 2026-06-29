from .analysis import Analysis, parse_analysis
from .prompt import SYSTEM_PROMPT, build_user_message
from .validate import ParsedEvent


def analyze(client, model_id: str, event: ParsedEvent) -> Analysis:
    response = client.converse(
        modelId=model_id,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[
            {"role": "user", "content": [{"text": build_user_message(event)}]}
        ],
        inferenceConfig={"maxTokens": 512, "temperature": 0.0},
    )
    text = response["output"]["message"]["content"][0]["text"]
    return parse_analysis(text)
