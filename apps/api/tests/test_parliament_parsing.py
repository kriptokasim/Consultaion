from parliament.engine import parse_seat_llm_output


def test_parse_valid_json_envelope():
    raw = '{"content": "Hello", "reasoning": "because", "stance": "support"}'
    env = parse_seat_llm_output(raw)
    assert env.content == "Hello"
    assert env.reasoning == "because"
    assert env.stance == "support"


def test_parse_json_missing_optional_fields():
    raw = '{"content": "Hi"}'
    env = parse_seat_llm_output(raw)
    assert env.content == "Hi"
    assert env.reasoning is None
    assert env.stance is None


def test_parse_invalid_json_falls_back():
    raw = "not json at all"
    env = parse_seat_llm_output(raw)
    assert env.content.startswith("not json")
    assert env.stance is None
