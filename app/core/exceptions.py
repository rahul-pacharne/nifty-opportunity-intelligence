"""Domain errors. Provider failures must not become recommendations."""


class NoiError(Exception):
    """Base error for recoverable NOI failures."""


class DataQualityError(NoiError):
    """An observation failed validation and was not stored as usable."""


class LookAheadError(NoiError):
    """A caller asked for data published after the decision timestamp."""


class ConfigurationError(NoiError):
    """Required configuration is missing or inconsistent."""
