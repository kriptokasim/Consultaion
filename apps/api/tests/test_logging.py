import json
import logging
from unittest.mock import MagicMock, patch
from log_config import JsonFormatter, DevFormatter, log_event

def test_json_formatter():
    formatter = JsonFormatter()
    record = logging.LogRecord("test", logging.INFO, "path", 10, "message", (), None)
    record.request_id = "req-123"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "message"
    assert data["request_id"] == "req-123"
    assert "timestamp" in data

def test_dev_formatter():
    formatter = DevFormatter()
    record = logging.LogRecord("test", logging.INFO, "path", 10, "message", (), None)
    record.request_id = "req-123"
    output = formatter.format(record)
    assert "[req-123]" in output
    assert "INFO" in output
    assert "message" in output

@patch("logging.Logger.log")
def test_log_event(mock_log):
    with patch("config.settings.IS_LOCAL_ENV", False):
        log_event("test.event", user_id="123")
        mock_log.assert_called_once()
        args = mock_log.call_args
        payload = json.loads(args[0][1])
        assert payload["event"] == "test.event"
        assert payload["user_id"] == "123"
        assert "request_id" in payload
