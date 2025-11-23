from parliament.engine import SeatTurn, _build_seat_message_event
from agents import UsageCall


def test_build_seat_message_event_includes_seat_metadata():
    turn = SeatTurn(
        seat_id="seat-1",
        seat_name="Optimist",
        role_profile="optimist",
        round_index=1,
        phase="explore",
        provider="mock",
        model="mock-model",
        content="Hello world",
        stance="support",
        reasoning=None,
        usage=UsageCall(total_tokens=10, provider="mock", model="mock-model"),
    )
    event = _build_seat_message_event("deb-123", turn)
    assert event["type"] == "seat_message"
    assert event["debate_id"] == "deb-123"
    assert event["round"] == 1
    assert event["seat_id"] == "seat-1"
    assert event["seat"]["seat_id"] == "seat-1"
    assert event["seat"]["role_id"] == "optimist"
    assert event["seat"]["provider"] == "mock"
    assert event["seat"]["model"] == "mock-model"
    assert event["seat"]["stance"] == "support"
    assert event["content"] == "Hello world"
