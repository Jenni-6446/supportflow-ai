from abc import ABC, abstractmethod

from app.schemas.analysis import InitialTriageResponse
from app.schemas.diagnosis import ChecklistResult, UpdatedDiagnosisResponse
from app.schemas.documentation import DocumentationResponse
from app.schemas.ticket import TicketInput


class AIProvider(ABC):
    @abstractmethod
    def analyze_ticket(self, ticket: TicketInput) -> InitialTriageResponse:
        raise NotImplementedError

    @abstractmethod
    def update_diagnosis(
        self,
        ticket: TicketInput,
        checklist_results: list[ChecklistResult],
    ) -> UpdatedDiagnosisResponse:
        raise NotImplementedError

    @abstractmethod
    def generate_documentation(
        self,
        ticket: TicketInput,
        diagnosis: UpdatedDiagnosisResponse,
    ) -> DocumentationResponse:
        raise NotImplementedError
