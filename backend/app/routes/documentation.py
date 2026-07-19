from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.schemas.diagnosis import UpdatedDiagnosisResponse
from app.schemas.documentation import DocumentationResponse
from app.schemas.ticket import TicketInput
from app.services.ai_provider_factory import get_ai_provider


class GenerateDocumentationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ticket: TicketInput
    diagnosis: UpdatedDiagnosisResponse


router = APIRouter(prefix="/api", tags=["documentation"])
provider = get_ai_provider()


@router.post("/generate-documentation", response_model=DocumentationResponse)
def generate_documentation(
    request: GenerateDocumentationRequest,
) -> DocumentationResponse:
    return provider.generate_documentation(request.ticket, request.diagnosis)
