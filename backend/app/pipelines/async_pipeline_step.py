from abc import abstractmethod
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from app.pipelines.pipeline_step_base import PipelineStepBase

Context = TypeVar("Context")

if TYPE_CHECKING:
    from app.pipelines.pipeline_cursor import PipelineCursor


@runtime_checkable
class AsyncPipelineStep(PipelineStepBase[Context], Protocol[Context]):  # type: ignore[misc]
    REQUIRES: tuple[type, ...] = ()

    def __init__(self):
        self.is_awaitable = True

    @abstractmethod
    async def run_async(self, context: Context):
        """Overwrite `run_async` to add logic to be executed asynchronous in a pipeline."""
        ...

    async def execute_async(self, context: Context, next_step: "PipelineCursor"):
        """Do not overwrite `execute_async`!"""
        for required in self.REQUIRES:
            if not isinstance(context, required):
                raise TypeError(
                    f"{type(self).__name__} requires {required.__name__} "
                    f"but got {type(context).__name__}"
                )
        await self.run_async(context)
        await next_step.run_async(context)

    async def compensate_async(self, context: Context) -> None:
        """Override to undo this step's side effects when a later step fails.

        Called by the pipeline cursor in reverse step order whenever a
        ``PipelineError`` propagates past this step. The default implementation
        is a no-op — only steps with external side effects (writes to a
        filesystem, database, or object storage) need to override this.
        """
        ...
