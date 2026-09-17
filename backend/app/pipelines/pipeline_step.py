from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from app.pipelines.pipeline_step_base import PipelineStepBase

Context = TypeVar("Context")

if TYPE_CHECKING:
    from app.pipelines.pipeline_cursor import PipelineCursor


@runtime_checkable
class PipelineStep(PipelineStepBase[Context], Protocol[Context]):  # type: ignore[misc]
    REQUIRES: tuple[type, ...] = ()

    def __init__(self):
        self.is_awaitable = False

    def __call__(self, context: Context) -> None:
        """Overwrite `__call__` to add logic to be executed in a pipeline."""
        ...

    async def run(self, context: Context, next_step: "PipelineCursor") -> None:
        """Do not overwrite `run`!"""
        for required in self.REQUIRES:
            if not isinstance(context, required):
                raise TypeError(
                    f"{type(self).__name__} requires {required.__name__} "
                    f"but got {type(context).__name__}"
                )
        self(context)
        await next_step.run_async(context)
