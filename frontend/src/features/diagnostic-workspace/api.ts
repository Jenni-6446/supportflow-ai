import type {
  ChecklistResult,
  DocumentationResponse,
  InitialTriageResponse,
  TicketInput,
  UpdatedDiagnosisResponse
} from "./types";

async function postJson<TResponse>(
  path: string,
  body: unknown
): Promise<TResponse> {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Request failed (${response.status}): ${detail}`);
  }

  return response.json() as Promise<TResponse>;
}

export function analyzeTicket(
  ticket: TicketInput
): Promise<InitialTriageResponse> {
  return postJson<InitialTriageResponse>("/api/analyze-ticket", ticket);
}

export function updateDiagnosis(
  ticket: TicketInput,
  checklistResults: ChecklistResult[]
): Promise<UpdatedDiagnosisResponse> {
  return postJson<UpdatedDiagnosisResponse>("/api/update-diagnosis", {
    ticket,
    checklistResults
  });
}

export function generateDocumentation(
  ticket: TicketInput,
  diagnosis: UpdatedDiagnosisResponse
): Promise<DocumentationResponse> {
  return postJson<DocumentationResponse>("/api/generate-documentation", {
    ticket,
    diagnosis
  });
}
