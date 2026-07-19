from fastapi import APIRouter

from app.schemas.analysis import InitialTriageResponse
from app.schemas.ticket import TicketInput
from app.services.ai_provider_factory import get_ai_provider


router = APIRouter(prefix="/api", tags=["analysis"])
provider = get_ai_provider()


@router.post("/analyze-ticket", response_model=InitialTriageResponse)
def analyze_ticket(ticket: TicketInput) -> InitialTriageResponse:
    return provider.analyze_ticket(ticket)
