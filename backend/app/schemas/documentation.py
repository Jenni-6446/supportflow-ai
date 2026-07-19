from pydantic import BaseModel, ConfigDict, Field


class DocumentationResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    internal_note: str = Field(alias="internalNote", min_length=1)
    user_response_draft: str = Field(alias="userResponseDraft", min_length=1)
    resolution_note: str = Field(alias="resolutionNote", min_length=1)
    escalation_note: str = Field(alias="escalationNote", min_length=1)
