class TransientLLMError(Exception):
    """Represents a transient/temporary LLM failure eligible for retry."""

    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause
