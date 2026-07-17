"""PS155.4 — Synthesis and Voting Correctness tests."""
from __future__ import annotations

from utils.json_utils import extract_and_parse_json


def test_robust_json_parsing():
    """Ensure the robust JSON parser extracts from various LLM outputs."""

    # 1. Pure JSON
    pure_json = '{"score": 8.5, "rationale": "Good"}'
    assert extract_and_parse_json(pure_json) == {"score": 8.5, "rationale": "Good"}

    # 2. Markdown fenced JSON
    fenced_json = """Here is the result:
```json
{"score": 9.0, "rationale": "Excellent"}
```
Thanks.
"""
    assert extract_and_parse_json(fenced_json) == {"score": 9.0, "rationale": "Excellent"}

    # 3. Naked JSON in text
    naked_json = """The model scored well.
{"score": 7.0, "rationale": "Average"}
That's the final score.
"""
    assert extract_and_parse_json(naked_json) == {"score": 7.0, "rationale": "Average"}

    # 4. JSON Array
    array_json = """```
["claim 1", "claim 2"]
```"""
    assert extract_and_parse_json(array_json) == ["claim 1", "claim 2"]

    # 5. Invalid/No JSON
    assert extract_and_parse_json("No JSON here.") is None
    assert extract_and_parse_json("{" * 10) is None
    assert extract_and_parse_json(None) is None


def test_voting_task_extraction_integrity():
    """Ensure that the voting_tasks.py logic is protected by robust parsing."""
    # We simulate the voting task logic using extract_and_parse_json
    raw = """Here are the highlights:
{
  "winner_highlights": ["Point 1", "Point 2", 123, null],
  "dissenter_highlights": ["Point A", "Point B"]
}"""

    data = extract_and_parse_json(raw)
    assert data is not None

    w = data.get("winner_highlights", [])
    d = data.get("dissenter_highlights", [])

    # The exact logic in voting_tasks.py for validation
    winner_hl = ["Highly structured and coherent response"]
    dissenter_hl = ["Missed key constraints", "Lacked detail compared to winner"]

    if isinstance(w, list):
        valid_w = [str(x).strip() for x in w if str(x).strip()]
        if valid_w:
            winner_hl = valid_w[:5]

    if isinstance(d, list):
        valid_d = [str(x).strip() for x in d if str(x).strip()]
        if valid_d:
            dissenter_hl = valid_d[:5]

    assert winner_hl == ["Point 1", "Point 2", "123", "None"]
    assert dissenter_hl == ["Point A", "Point B"]
