"""Versioned deterministic policy for research-only instructional design."""

from pydantic import BaseModel, ConfigDict, Field

from app.instructional_design.schemas import CognitiveProcess


class InstructionalDesignPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    cognitive_order: tuple[CognitiveProcess, ...]
    obvious_non_observable_prefixes: tuple[str, ...]

    def cognitive_rank(self, cognitive_process: CognitiveProcess) -> int:
        return self.cognitive_order.index(cognitive_process)


INSTRUCTIONAL_DESIGN_POLICY_V0_1 = InstructionalDesignPolicy(
    policy_id="pai_instructional_design",
    policy_version="0.1",
    cognitive_order=(
        CognitiveProcess.REMEMBER,
        CognitiveProcess.UNDERSTAND,
        CognitiveProcess.APPLY,
        CognitiveProcess.ANALYZE,
        CognitiveProcess.EVALUATE,
        CognitiveProcess.CREATE,
    ),
    obvious_non_observable_prefixes=(
        "understand ",
        "know ",
        "learn ",
        "become familiar with ",
    ),
)
