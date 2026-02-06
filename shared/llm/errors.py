"""LLM data collection errors."""


class DataUnavailableError(RuntimeError):
    """Raised when a required data source is unavailable."""

    def __init__(self, source: str, detail: str | None = None):
        self.source = source
        self.detail = detail or ""
        msg = f"{source}: {self.detail}" if self.detail else source
        super().__init__(msg)
