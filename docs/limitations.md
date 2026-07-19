# Limitations and Safety Boundaries

SupportFlow AI is a portfolio prototype for assisted intake and triage. It is not a production service desk, autonomous diagnostic system, or source of confirmed root cause.

## Integration Boundaries

The project is not connected to Jira, ServiceNow, Microsoft 365, Intune, Active Directory, endpoint-management tools, administrative portals, logs, network infrastructure, telephony systems, or vendor platforms. It cannot verify their state.

## Analysis Boundaries

LLM-assisted semantic interpretation requires a configured key, model, and compatible endpoint. Generated output is untrusted until it passes schema and safety validation. The fallback provider is deterministic and intentionally limited; it cannot understand every phrasing or environment.

The application can suggest categories, missing details, likely support directions, and Level 1 checks. These are working triage aids, not evidence that a cause has been proven.

## Operational Boundaries

The prototype does not yet include production authentication, authorization, audit logging, rate limiting, persistent ticket storage, privacy controls, observability, high-availability design, or formal security review.

## Future Evidence Awareness

Evidence-aware diagnosis is an experimental direction. Future integrations should identify the source and freshness of evidence, preserve uncertainty, require least-privilege access, provide an audit trail, and keep a human reviewer responsible for support decisions.
