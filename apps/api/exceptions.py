"""
Custom exceptions for Consultaion.

Patchsets 28.0 & 29.0
"""


class ProviderCircuitOpenError(RuntimeError):
    """
    Raised when circuit breaker is open for a provider/model.
    
    Indicates the provider/model has exceeded error thresholds
    and calls are temporarily blocked to prevent cascading failures.
    
    Patchset 28.0
    """
    pass
