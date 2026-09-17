from typing import Protocol, TypeVar

Context = TypeVar("Context")


class PipelineStepBase(Protocol[Context]):  # type: ignore[misc]
    """Base implementation for pipeline steps"""

    """This flag is used to distinguish whether the step is called asynchronously (with await) or synchronously."""
    is_awaitable: bool
