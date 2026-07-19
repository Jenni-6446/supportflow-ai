# Architecture

SupportFlow AI is a local web prototype with a React frontend and a FastAPI backend. Its boundaries deliberately keep generative analysis separate from controlled support workflow logic.

## Frontend

The React and TypeScript application under `frontend/` provides ticket intake, clarification, guided checks, diagnosis updates, and copyable documentation. Vite serves the development app and proxies `/api` calls to the backend.

## Backend

FastAPI routes under `backend/app/routes/` expose ticket analysis, diagnosis updates, documentation generation, and health checking. Pydantic schemas validate request and response shapes at the API boundary.

## Provider Boundary

`AIProvider` defines the analysis, diagnosis-update, and documentation operations used by the routes.

- `StructuredLLMAnalyzeProvider` uses a configured OpenAI-compatible endpoint for structured analysis. It parses and validates output before allowing it into the workflow.
- `MockAIProvider` provides deterministic classification, questions, checks, and notes. It is also the safe fallback when the configured LLM is unavailable, invalid, low confidence, or unsafe.

The current structured provider applies LLM interpretation to initial ticket analysis. Diagnosis updates and documentation remain delegated to the deterministic provider.

## Controlled Triage Logic

Playbooks define bounded Level 1 checks, evidence prompts, escalation metadata, and stable step identifiers. Question selectors combine category context with extracted signals such as application/service, attempted action, and failure mode. This improves relevance without allowing generated content to invent system access.

## Safety Validation

Structured output is schema-validated and checked for unsupported claims. Responses that imply real logs, administrative systems, accounts, devices, networks, or vendor platforms were checked are rejected. The application presents likely directions and working hypotheses, never a confirmed root cause.

## Tests

Backend tests cover:

- request and response schemas
- FastAPI routes
- deterministic provider behavior
- structured-provider parsing, validation, and fallback
- category and signal-based question selection
- evidence-aware diagnosis behavior

The frontend currently relies on TypeScript compilation and the production build as its automated verification; dedicated frontend tests are a future improvement.
