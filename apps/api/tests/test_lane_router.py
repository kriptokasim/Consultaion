import pytest
from coding_agent.lane_router import classify_tier, TierThresholds, RISK_KEYWORDS

def test_classify_tier_0_trivial():
    res = classify_tier(["app/main.py"], "Change the background color to red")
    assert res.tier == 0
    assert res.active_lanes == ["fast"]
    assert len(res.risk_signals) == 0

def test_classify_tier_1_moderate():
    # Long prompt
    long_prompt = "x" * 250
    res = classify_tier(["app/main.py"], long_prompt)
    assert res.tier == 1
    assert "fast" in res.active_lanes
    assert "thinking" in res.active_lanes

    # Moderate file count
    res = classify_tier(["file1.py", "file2.py", "file3.py"], "Update imports")
    assert res.tier == 1
    assert "fast" in res.active_lanes
    assert "thinking" in res.active_lanes

def test_classify_tier_2_risk_keywords():
    # Auth keyword in prompt
    res = classify_tier(["app/main.py"], "Add google oauth integration")
    assert res.tier == 2
    assert res.active_lanes == ["fast", "thinking", "verifier", "judge"]
    assert "oauth" in res.risk_signals

    # CI.yml file path
    res = classify_tier([".github/workflows/ci.yml"], "Update python version")
    assert res.tier == 2
    assert res.active_lanes == ["fast", "thinking", "verifier", "judge"]
    assert "ci.yml" in res.risk_signals

def test_classify_tier_2_complexity():
    # Risky file count
    files = [f"file{i}.py" for i in range(10)]
    res = classify_tier(files, "Refactor everything")
    assert res.tier == 2
    assert "judge" in res.active_lanes

    # Risky prompt length
    long_prompt = "x" * 1500
    res = classify_tier(["app/main.py"], long_prompt)
    assert res.tier == 2
    assert "judge" in res.active_lanes
