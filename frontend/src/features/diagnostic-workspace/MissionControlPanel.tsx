import type {
  ChecklistGroup,
  InitialTriageResponse,
  UpdatedDiagnosisResponse
} from "./types";

interface MissionControlPanelProps {
  triage: InitialTriageResponse | null;
  diagnosis: UpdatedDiagnosisResponse | null;
}

const layerLabels: Record<ChecklistGroup, string> = {
  scope_impact: "Scope & Impact",
  simple_user_checks: "Simple User Checks",
  device_client_application: "Device / Client / Application",
  platform_permission_configuration: "Platform / Permission / Configuration",
  escalation_admin_infrastructure: "Escalation / Admin / Infrastructure"
};

function formatValue(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function statusText(value: boolean | undefined): string {
  if (typeof value !== "boolean") {
    return "Pending";
  }
  return value ? "Yes" : "No";
}

export function MissionControlPanel({
  triage,
  diagnosis
}: MissionControlPanelProps) {
  const escalationRequired =
    diagnosis?.escalationRecommendation.shouldEscalate ?? false;
  const currentLayer = diagnosis?.currentTroubleshootingLayer;
  const hasDiagnosis = Boolean(diagnosis);
  const nextAction =
    diagnosis?.nextBestAction ??
    (triage ? "Record checklist evidence and update diagnosis." : "Analyze a ticket to begin.");

  return (
    <section className="mission-control" aria-label="Case mission control">
      <div className="mission-cell mission-cell-wide">
        <span className="mission-label">Category</span>
        <strong>
          {triage ? formatValue(triage.classification.category) : "Not analyzed"}
        </strong>
        <span className="mission-meta">
          {triage?.classification.subcategory ?? "No triage yet"}
        </span>
      </div>
      <div className="mission-cell">
        <span className="mission-label">Priority</span>
        <strong>{triage?.priorityAssessment.priority ?? "Pending"}</strong>
        <span className="mission-meta">
          {triage ? formatValue(triage.priorityAssessment.confidence) : "Unknown"}
        </span>
      </div>
      <div className="mission-cell mission-cell-wide">
        <span className="mission-label">Current layer</span>
        <strong>
          {currentLayer
            ? layerLabels[currentLayer]
            : triage
              ? "Awaiting diagnosis update"
              : "Awaiting evidence"}
        </strong>
        <span className="mission-meta">
          {diagnosis?.completedLayers?.length
            ? `${diagnosis.completedLayers.length} layer(s) completed`
            : triage
              ? "Record evidence, then update diagnosis"
              : "No completed layers yet"}
        </span>
      </div>
      <div
        className={`mission-cell ${
          diagnosis?.level1CanContinue === false ? "mission-warning" : ""
        }`}
      >
        <span className="mission-label">Level 1 can continue</span>
        <strong>{statusText(diagnosis?.level1CanContinue)}</strong>
        <span className="mission-meta">
          {!hasDiagnosis
            ? "Awaiting diagnosis update"
            : diagnosis?.level1CanContinue === false
              ? "Privileged review boundary"
              : "Within guided checks"}
        </span>
      </div>
      <div className={`mission-cell ${escalationRequired ? "mission-danger" : ""}`}>
        <span className="mission-label">Escalation</span>
        <strong>{diagnosis ? (escalationRequired ? "Required" : "Not yet") : "Pending"}</strong>
        <span className="mission-meta">
          {!hasDiagnosis
            ? "Awaiting diagnosis update"
            : escalationRequired
              ? "Escalate with collected evidence"
              : "Continue evidence path"}
        </span>
      </div>
      <div className="mission-cell mission-next-action">
        <span className="mission-label">Next best action</span>
        <strong>{nextAction}</strong>
      </div>
    </section>
  );
}
