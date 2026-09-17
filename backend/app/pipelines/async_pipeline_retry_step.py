import asyncio
import logging
from typing import TypeVar

from app.pipelines.async_pipeline_step import AsyncPipelineStep

logger = logging.getLogger(__name__)

Context = TypeVar("Context")


class AsyncRetryPipelineStep(AsyncPipelineStep):
    """Wraps a step with retry + exponential backoff on a given exception set.

    Use for steps calling a flaky external service (e.g. the Docling server
    over a lossy network link) where a transient failure shouldn't fail the
    whole document.
    """

    _inner_step: AsyncPipelineStep
    is_awaitable: bool
    retries: int
    retry_backoff: float

    def __init__(
        self,
        innerStep: AsyncPipelineStep,
        on: tuple[type[Exception], ...],
        retries: int = 3,
        retry_backoff: float = 0.5,
    ):
        self._inner_step = innerStep
        self.is_awaitable = True
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.on = on

    @property  # type: ignore[override]
    def REQUIRES(self) -> tuple[type, ...]:  # type: ignore[override]
        return self._inner_step.REQUIRES

    @property
    def step_name(self) -> str:
        return type(self._inner_step).__name__

    async def run_async(self, context: Context):
        attempt = 0
        while True:
            try:
                await self._inner_step.run_async(context)
                break  # Success, exit the loop
            except Exception as e:
                if not isinstance(e, self.on):
                    raise  # Exception type not in 'on', re-raise immediately
                attempt += 1

                if attempt > self.retries:
                    logger.warning(
                        "Step %s failed after %d attempt(s), giving up: %s",
                        type(self._inner_step).__name__,
                        attempt,
                        e,
                    )
                    raise  # Exceeded max retries, re-raise the exception

                delay = self.retry_backoff * (2 ** (attempt - 1))
                logger.warning(
                    "Step %s failed (attempt %d/%d): %s — retrying in %.2fs",
                    type(self._inner_step).__name__,
                    attempt,
                    self.retries,
                    e,
                    delay,
                )
                await asyncio.sleep(delay)

    async def compensate_async(self, context: Context):
        await self._inner_step.compensate_async(context)
