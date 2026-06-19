from correlation import (
    CorrelationContext,
    create_child_context,
    current_correlation,
    ensure_correlation,
    get_correlation_context,
    set_correlation_context,
)


def test_correlation_context_generates_ids():
    ctx = CorrelationContext()
    assert ctx.request_id.startswith("req-")
    assert ctx.trace_id.startswith("trace-")


def test_correlation_context_with_debate():
    ctx = CorrelationContext(user_id="u1")
    child = ctx.with_debate("d1")
    assert child.debate_id == "d1"
    assert child.user_id == "u1"
    assert ctx.debate_id is None


def test_correlation_context_with_attempt():
    ctx = CorrelationContext(trace_id="trace-abc")
    child = ctx.with_attempt("a1")
    assert child.attempt_id == "a1"
    assert child.trace_id == "trace-abc"


def test_correlation_context_to_log_fields():
    ctx = CorrelationContext(user_id="u1", debate_id="d1")
    fields = ctx.to_log_fields()
    assert "request_id" in fields
    assert fields["user_id"] == "u1"
    assert fields["debate_id"] == "d1"
    assert "attempt_id" not in fields


def test_correlation_context_to_headers():
    ctx = CorrelationContext(request_id="req-123", trace_id="trace-456")
    headers = ctx.to_headers()
    assert headers["X-Request-ID"] == "req-123"
    assert headers["X-Trace-ID"] == "trace-456"


def test_correlation_context_to_sse_metadata():
    ctx = CorrelationContext(debate_id="d1", attempt_id="a1")
    meta = ctx.to_sse_metadata()
    assert meta["debate_id"] == "d1"
    assert meta["attempt_id"] == "a1"
    assert "user_id" not in meta


def test_contextvar_roundtrip():
    token = set_correlation_context(CorrelationContext(user_id="u1"))
    try:
        ctx = get_correlation_context()
        assert ctx is not None
        assert ctx.user_id == "u1"
    finally:
        set_correlation_context(token)


def test_current_correlation_creates_if_missing():
    original = get_correlation_context()
    token = set_correlation_context(None)
    try:
        ctx = current_correlation()
        assert ctx is not None
        assert ctx.request_id.startswith("req-")
    finally:
        set_correlation_context(token)


def test_ensure_correlation_preserves_existing():
    original = CorrelationContext(user_id="existing")
    token = set_correlation_context(original)
    try:
        ctx = ensure_correlation(user_id="new_user")
        assert ctx.user_id == "existing"
    finally:
        set_correlation_context(token)


def test_ensure_correlation_sets_user_when_missing():
    original = get_correlation_context()
    token = set_correlation_context(None)
    try:
        ctx = ensure_correlation(user_id="u1")
        assert ctx.user_id == "u1"
    finally:
        set_correlation_context(token)


def test_create_child_context_merges_parent():
    original = get_correlation_context()
    parent = CorrelationContext(trace_id="trace-parent", user_id="u1")
    token = set_correlation_context(parent)
    try:
        child = create_child_context(debate_id="d1", task_id="t1")
        assert child.trace_id == "trace-parent"
        assert child.user_id == "u1"
        assert child.debate_id == "d1"
        assert child.task_id == "t1"
    finally:
        set_correlation_context(token)


def test_create_child_context_without_parent():
    original = get_correlation_context()
    token = set_correlation_context(None)
    try:
        child = create_child_context(user_id="u1")
        assert child.user_id == "u1"
        assert child.trace_id.startswith("trace-")
    finally:
        set_correlation_context(token)
