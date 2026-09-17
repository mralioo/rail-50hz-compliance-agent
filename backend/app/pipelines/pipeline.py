from typing import Generic, TypeVar, Union

from app.pipelines.async_pipeline_step import AsyncPipelineStep
from app.pipelines.pipeline_cursor import PipelineCursor
from app.pipelines.pipeline_step import PipelineStep

T = TypeVar("T")


class Pipeline(Generic[T]):
    def __init__(self, *steps: Union[PipelineStep, AsyncPipelineStep]):
        self.queue = [step for step in steps]

    def append(self, step: Union[PipelineStep, AsyncPipelineStep]) -> None:
        self.queue.append(step)

    async def run_async(self, context: T) -> None:
        execute = PipelineCursor(self.queue)
        return await execute.run_async(context)

    def __len__(self) -> int:
        return len(self.queue)
