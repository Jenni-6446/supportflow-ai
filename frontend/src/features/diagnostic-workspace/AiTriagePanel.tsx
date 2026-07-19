import type { InitialTriageResponse } from "./types";

interface AiTriagePanelProps {
  triage: InitialTriageResponse | null;
}

export function AiTriagePanel({ triage }: AiTriagePanelProps) {
  if (!triage) {
    return (
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Issue Understanding</h2>
            <p className="panel-subtitle">Structured analysis appears after ticket review.</p>
          </div>
        </div>
        <div className="panel-body">
          <div className="empty-state">Analyze a ticket to view triage details.</div>
        </div>
      </section>
    );
  }

  const priorityNeedsConfirmation =
    triage.priorityAssessment.impact === "unknown" ||
    triage.priorityAssessment.urgency === "unknown" ||
    triage.priorityAssessment.priority === "unknown";
  const visibleHypotheses = triage.possibleCauses.slice(0, 2);

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Issue Understanding</h2>
          <p className="panel-subtitle">A short summary before narrowing the issue.</p>
        </div>
      </div>
      <div className="panel-body">
        <div className="triage-summary">
          <span className="section-kicker">I understand this as</span>
          <p>{triage.summary}</p>
        </div>
        {priorityNeedsConfirmation ? (
          <div className="priority-confirmation">
            <span className="section-kicker">Priority</span>
            <h3>Priority needs confirmation</h3>
            <p>
              Impact and urgency details are needed before assigning priority.
            </p>
            <p>
              Priority is estimated from impact and urgency. Impact means how
              many users, services, or business processes are affected. Urgency
              means how quickly the issue must be resolved.
            </p>
          </div>
        ) : null}
        {visibleHypotheses.length > 0 ? (
          <div className="content-section">
            <h3>Possible starting points</h3>
            <p className="section-helper">
              These are starting points, not confirmed causes.
            </p>
            <ul className="list">
              {visibleHypotheses.map((item, index) => (
                <li key={`${item.cause}-${index}`}>
                  <span className="hypothesis-label">Needs confirmation</span>
                  <span className="item-title">{item.cause}</span>
                  <span className="item-meta">{item.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
