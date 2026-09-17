"""Structured error raised when a pipeline step fails."""


class PipelineError(Exception):
    """Wraps an exception raised by a pipeline step with step-level context.

    Attributes:
        failed_step: Class name of the step that raised the exception.
        cause: The original exception.
    """

    def __init__(self, failed_step: str, cause: Exception) -> None:
        super().__init__(f"Pipeline failed at step '{failed_step}': {cause}")
        self.failed_step = failed_step
        self.cause = cause
