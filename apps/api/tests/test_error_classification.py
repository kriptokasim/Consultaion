from exceptions import ConfigurationError, ProviderCircuitOpenError


def test_configuration_error_is_non_retryable_internal_failure():
    error = ConfigurationError(
        message="missing server config",
        code="auth.configuration_error",
    )

    assert error.status_code == 500
    assert error.retryable is False


def test_legacy_auth_configuration_path_does_not_look_like_provider_outage():
    error = ProviderCircuitOpenError(
        message="Web application origin is not configured",
        code="auth.configuration_error",
    )

    assert error.status_code == 500
    assert error.retryable is False
    assert error.hint == "Server configuration requires operator action."


def test_real_provider_circuit_error_remains_retryable_503():
    error = ProviderCircuitOpenError()

    assert error.status_code == 503
    assert error.retryable is True
