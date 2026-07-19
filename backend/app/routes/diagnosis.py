from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.diagnosis import ChecklistResult, UpdatedDiagnosisResponse
from app.schemas.ticket import TicketInput
from app.services.ai_provider_factory import get_ai_provider


class UpdateDiagnosisRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ticket: TicketInput
    checklist_results: list[ChecklistResult] = Field(alias="checklistResults")


router = APIRouter(prefix="/api", tags=["diagnosis"])
provider = get_ai_provider()


@router.post("/update-diagnosis", response_model=UpdatedDiagnosisResponse)
def update_diagnosis(request: UpdateDiagnosisRequest) -> UpdatedDiagnosisResponse:
    return provider.update_diagnosis(request.ticket, request.checklist_results)
