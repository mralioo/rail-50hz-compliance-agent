from dataclasses import dataclass, field


@dataclass(kw_only=True)
class BasePipelineContext:
    executed_steps: list[str] = field(default_factory=list)
