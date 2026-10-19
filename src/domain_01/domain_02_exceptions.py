"""Domain flow 02: exceptions mapped to safe API responses."""


class ApplicationError(Exception):
    """Base class for expected application failures."""


class ConfigurationError(ApplicationError):
    """Required local configuration is invalid or missing."""


class IndexNotReadyError(ApplicationError):
    """The local vector index is absent or incompatible."""


class SensitiveInputError(ApplicationError):
    """A question contains a recognizable personal identifier."""


class QuestionTooLongError(ApplicationError):
    """A question exceeds the embedding encoder limit."""


class UpstreamError(ApplicationError):
    """Base class for OpenRouter failures."""


class UpstreamTimeoutError(UpstreamError):
    """OpenRouter does not respond before the configured deadline."""


class UpstreamRateLimitError(UpstreamError):
    """OpenRouter rejects a request because of rate limits."""


class UpstreamUnavailableError(UpstreamError):
    """No eligible provider endpoint can serve the request."""


class UpstreamResponseError(UpstreamError):
    """OpenRouter returns an unusable response."""
