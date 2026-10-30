"""입력 규칙. 한 문장으로 시키기의 문장 길이 규칙을 한곳에 둔다."""

COMMAND_MIN = 1
COMMAND_MAX = 200


def check_command_text(v: str) -> str:
    """앞뒤 공백을 뗀 문장이 1~200자여야 한다. 아니면 ValueError(이유)."""
    v = v.strip()
    if len(v) < COMMAND_MIN:
        raise ValueError("시킬 내용을 입력해 주세요.")
    if len(v) > COMMAND_MAX:
        raise ValueError(f"시킬 내용은 {COMMAND_MAX}자 이하로 입력해 주세요.")
    return v
