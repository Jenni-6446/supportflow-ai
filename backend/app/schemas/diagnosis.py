from datetime import datetime
from enum import Enum

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.analysis import ChecklistGroup, Confidence


class ChecklistResultValue(str, Enum):
    WORKS = "works"
    DOES_NOT_WORK = "does_not_work"
    YES = "yes"
    NO = "no"
    NOT_TESTED = "not_tested"
    USER_UNSURE = "user_unsure"
    NEEDS_ESCALATION = "needs_escalation"


class DiagnosticStatus(str, Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    IN_PROGRESS = "in_progress"
    READY_TO_RESOLVE = "ready_to_resolve"
    READY_TO_ESCALATE = "ready_to_escalate"


class ChecklistResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    step_id: str = Field(alias="stepId", min_length=1)
    result: ChecklistResultValue
    evidence: str = Field(default="")
    recorded_at: datetime = Field(alias="recordedAt")

    @field_validator("recorded_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("recordedAt must be timezone-aware")
        return value


class CurrentLikelyCause(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cause: str = Field(min_length=1)
    confidence: Confidence
    reasoning: str = Field(min_length=1)


class RuledOutCause(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cause: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class EscalationRecommendation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    should_escalate: bool = Field(alias="shouldEscalate")
    reason: str = Field(min_length=1)


class MissingEvidenceItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    step_id: str = Field(alias="stepId", min_length=1)
    layer: ChecklistGroup
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class UpdatedDiagnosisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    current_likely_cause: CurrentLikelyCause = Field(alias="currentLikelyCause")
    ruled_out_causes: list[RuledOutCause] = Field(alias="ruledOutCauses")
    evidence_summary: list[str] = Field(alias="evidenceSummary")
    next_best_action: str = Field(alias="nextBestAction", min_length=1)
    current_troubleshooting_layer: ChecklistGroup | None = Field(
        default=None,
        alias="currentTroubleshootingLayer",
    )
    completed_layers: list[ChecklistGroup] = Field(
        default_factory=list,
        alias="completedLayers",
    )
    missing_evidence: list[MissingEvidenceItem] = Field(
        default_factory=list,
        alias="missingEvidence",
    )
    next_best_actions: list[str] = Field(
        default_factory=list,
        alias="nextBestActions",
    )
    level1_can_continue: bool = Field(default=True, alias="level1CanContinue")
    level1_blocker_reason: str = Field(default="", alias="level1BlockerReason")
    escalation_recommendation: EscalationRecommendation = Field(
        alias="escalationRecommendation"
    )
    confidence: Confidence
    status: DiagnosticStatus

    @model_validator(mode="after")
    def keep_next_best_action_compatible(self) -> Self:
        if not self.next_best_actions:
            self.next_best_actions = [self.next_best_action]
        elif self.next_best_actions[0] != self.next_best_action:
            self.next_best_action = self.next_best_actions[0]
        return self
