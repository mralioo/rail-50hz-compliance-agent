import logging
from typing import Generic, TypeVar, Union

from app.pipelines.async_pipeline_step import AsyncPipelineStep
from app.pipelines.pipeline_error import PipelineError
from app.pipelines.pipeline_step import PipelineStep

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PipelineCursor(Generic[T]):
    def __init__(self, steps: list[Union[PipelineStep, AsyncPipelineStep]]):
        self.queue = steps

    async def run_async(self, context: T):
        if not self.queue:
            return
        current_step = self.queue[0]
        next_step: PipelineCursor[T] = PipelineCursor(self.queue[1:])

        try:
            if current_step.is_awaitable:
                await current_step.execute_async(context, next_step)
            else:
                await current_step.run(context, next_step)
        except PipelineError:
            # Sync steps (is_awaitable=False) do not support compensation.
            if current_step.is_awaitable:
                try:
                    await current_step.compensate_async(context)
                except Exception:
                    logger.warning(
                        "compensate_async failed for %s",
                        getattr(current_step, "step_name", type(current_step).__name__),
                        exc_info=True,
                    )
            raise
        except Exception as e:
            raise PipelineError(
                failed_step=getattr(
                    current_step, "step_name", type(current_step).__name__
                ),
                cause=e,
            ) from e
