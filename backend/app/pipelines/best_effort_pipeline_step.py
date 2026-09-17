import logging
from typing import TypeVar

from app.pipelines.async_pipeline_step import AsyncPipelineStep

logger = logging.getLogger(__name__)

Context = TypeVar("Context")


class BestEffortPipelineStep(AsyncPipelineStep):
    """Wraps a step so that any exception is logged and swallowed.

    Use this for optional pipeline steps whose failure should not abort the
    rest of the pipeline (e.g. image extraction, which degrades gracefully to
    text-only when it fails).
    """

    def __init__(self, inner_step: AsyncPipelineStep) -> None:
        self._inner_step = inner_step
        self.is_awaitable = True

    @property  # type: ignore[override]
    def REQUIRES(self) -> tuple[type, ...]:  # type: ignore[override]
        return self._inner_step.REQUIRES

    @property
    def step_name(self) -> str:
        return type(self._inner_step).__name__

    async def run_async(self, context: Context) -> None:
        try:
            await self._inner_step.run_async(context)
        except Exception:
            logger.exception(
                "%s failed — continuing without this step",
                type(self._inner_step).__name__,
            )

    async def compensate_async(self, context: Context) -> None:
        await self._inner_step.compensate_async(context)
