import { useState } from "react";
import type {
  ChecklistGroup,
  ChecklistItem,
  ChecklistResult,
  ChecklistResultValue,
  InitialTriageResponse,
  UpdatedDiagnosisResponse
} from "./types";
import { checklistResultOptions } from "./types";

interface TroubleshootingBoardProps {
  triage: InitialTriageResponse | null;
  checklistResults: Record<string, ChecklistResult>;
  diagnosis: UpdatedDiagnosisResponse | null;
  isUpdating: boolean;
  error: string | null;
  onChecklistResultChange: (
    stepId: string,
    patch: Partial<ChecklistResult>
  ) => void;
  onUpdateDiagnosis: () => void;
}

function formatValue(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const checklistGroupLabels: Record<ChecklistGroup, string> = {
  scope_impact: "Scope & Impact",
  simple_user_checks: "Simple User Checks",
  device_client_application: "Device / Client / Application",
  platform_permission_configuration: "Platform / Permission / Configuration",
  escalation_admin_infrastructure: "Escalation / Admin Boundary"
};

const checklistRoundLabels: Record<ChecklistGroup, string> = {
  scope_impact: "Round 1",
  simple_user_checks: "Round 2",
  device_client_application: "Round 3",
  platform_permission_configuration: "Round 4",
  escalation_admin_infrastructure: "Final Boundary"
};

const checklistGroupOrder: ChecklistGroup[] = [
  "scope_impact",
  "simple_user_checks",
  "device_client_application",
  "platform_permission_configuration",
  "escalation_admin_infrastructure"
];

function groupChecklistItems(items: ChecklistItem[]) {
  const initialGroups: Record<ChecklistGroup, ChecklistItem[]> = {
    scope_impact: [],
    simple_user_checks: [],
    device_client_application: [],
    platform_permission_configuration: [],
    escalation_admin_infrastructure: []
  };

  const grouped = items.reduce<Record<ChecklistGroup, ChecklistItem[]>>(
    (groups, item) => {
      const group = item.group ?? "scope_impact";
      groups[group].push(item);
      return groups;
    },
    initialGroups
  );

  return checklistGroupOrder
    .map((group) => ({
      group,
      items: grouped[group]
    }))
    .filter((section) => section.items.length > 0);
}

function isRecorded(result: ChecklistResult | undefined): boolean {
  return Boolean(result && (result.result !== "not_tested" || result.evidence.trim()));
}

function formatRecordedAt(value: string | undefined): string {
  if (!value) {
    return "Recorded";
  }

  const recordedAt = new Date(value);
  if (Number.isNaN(recordedAt.getTime())) {
    return "Recorded";
  }

  return `Recorded at ${recordedAt.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit"
  })}`;
}

function LayerStepper({
  triage,
  diagnosis
}: {
  triage: InitialTriageResponse | null;
  diagnosis: UpdatedDiagnosisResponse | null;
}) {
  const completedLayers = new Set(diagnosis?.completedLayers ?? []);
  const missingLayers = new Set(
    (diagnosis?.missingEvidence ?? []).map((item) => item.layer)
  );
  const currentLayer: ChecklistGroup | null =
    diagnosis?.currentTroubleshootingLayer ?? (triage ? "scope_impact" : null);

  return (
    <div className="layer-stepper" aria-label="Troubleshooting layers">
      {checklistGroupOrder.map((layer, index) => {
        const isCurrent = currentLayer === layer;
        const isComplete = completedLayers.has(layer);
        const hasMissing = missingLayers.has(layer);
        const isEscalation = layer === "escalation_admin_infrastructure";
        const stateClass = isComplete
          ? "layer-complete"
          : isCurrent
            ? "layer-current"
            : hasMissing
              ? "layer-missing"
              : "";

        return (
          <div
            className={`layer-step ${stateClass} ${
              isEscalation ? "layer-escalation" : ""
            }`}
            key={layer}
          >
            <span className="layer-index">{index + 1}</span>
            <span className="layer-name">{checklistGroupLabels[layer]}</span>
            <span className="layer-state">
              {isComplete
                ? "Completed"
                : isCurrent
                  ? "Current"
                  : hasMissing
                    ? "Missing evidence"
                    : "Not reached"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function EscalationBoundaryPanel({
  diagnosis
}: {
  diagnosis: UpdatedDiagnosisResponse;
}) {
  const shouldShow =
    diagnosis.level1CanContinue === false ||
    diagnosis.escalationRecommendation.shouldEscalate;

  if (!shouldShow) {
    return null;
  }

  const nextActions = (diagnosis.nextBestActions ?? []).slice(0, 2);
  const escalationReason =
    diagnosis.level1BlockerReason ||
    diagnosis.escalationRecommendation.reason ||
    "Level 1 checks have reached a privileged review boundary.";

  return (
    <div className="escalation-panel">
      <div>
        <h3>Requires privileged review</h3>
        <span className="escalation-action-label">
          Escalate with collected evidence
        </span>
      </div>
      <p>{escalationReason}</p>
      {nextActions.length > 0 ? (
        <div>
          <h4>Next actions</h4>
          <ul>
            {nextActions.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function TroubleshootingBoard({
  triage,
  checklistResults,
  diagnosis,
  isUpdating,
  error,
  onChecklistResultChange,
  onUpdateDiagnosis
}: TroubleshootingBoardProps) {
  const currentLayer = diagnosis?.currentTroubleshootingLayer ?? "scope_impact";
  const visibleNextActions = diagnosis
    ? (diagnosis.nextBestActions && diagnosis.nextBestActions.length > 0
        ? diagnosis.nextBestActions
        : [diagnosis.nextBestAction]
      ).slice(0, 3)
    : [];
  const [expandedCheckGroups, setExpandedCheckGroups] = useState<
    Partial<Record<ChecklistGroup, boolean>>
  >({});

  const toggleExpandedCheckGroup = (group: ChecklistGroup) => {
    setExpandedCheckGroups((current) => ({
      ...current,
      [group]: !current[group]
    }));
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Guided Checks</h2>
          <p className="panel-subtitle">Record evidence for each diagnostic check.</p>
        </div>
      </div>
      <div className="panel-body">
        {error ? <div className="alert">{error}</div> : null}
        {!triage ? (
          <div className="empty-state">Analyze a ticket to generate checklist items.</div>
        ) : (
          <>
            <LayerStepper triage={triage} diagnosis={diagnosis} />
            <div className="checklist">
              {groupChecklistItems(triage.checklist).map((section) => {
                const isCurrentGroup = section.group === currentLayer;
                const showAllChecks = expandedCheckGroups[section.group] ?? false;
                const visibleItems = showAllChecks
                  ? section.items
                  : section.items.slice(0, 3);
                const hiddenCheckCount = section.items.length - visibleItems.length;
                return (
                <details
                  className={`check-group check-group-collapsible ${
                    isCurrentGroup ? "check-group-current" : "check-group-secondary"
                  }`}
                  key={section.group}
                  open={isCurrentGroup || undefined}
                >
                  <summary className="check-group-summary">
                    <span>
                      <strong>{checklistRoundLabels[section.group]}</strong>
                      {checklistGroupLabels[section.group]}
                    </span>
                    <span>
                      {isCurrentGroup ? "Current layer" : `${section.items.length} check(s)`}
                    </span>
                  </summary>
                  {visibleItems.map((item) => {
                    const result = checklistResults[item.id];
                    const recorded = isRecorded(result);
                    return (
                      <div
                        className={`check-item ${
                          item.requiresPrivilegedAccess ? "check-privileged" : ""
                        }`}
                        key={item.id}
                      >
                        <div className="check-item-header">
                          <div>
                            <h3>{item.step}</h3>
                            <p>{item.why}</p>
                          </div>
                          <span
                            className={`recording-state ${
                              recorded ? "recorded" : ""
                            }`}
                          >
                            {recorded
                              ? formatRecordedAt(result?.recordedAt)
                              : "Not recorded"}
                          </span>
                        </div>
                        <div className="badge-row">
                          <span className="badge">
                            {formatValue(item.expectedResultType)}
                          </span>
                          {item.level1Actionable === false ? (
                            <span className="badge badge-warning">
                              Level 1 boundary
                            </span>
                          ) : (
                            <span className="badge badge-success">
                              Level 1 actionable
                            </span>
                          )}
                          {item.requiresPrivilegedAccess ? (
                            <span className="badge badge-danger">
                              Requires privileged review
                            </span>
                          ) : null}
                        </div>
                        {item.accessRequirement ? (
                          <div className="access-note">
                            {item.accessRequirement}
                          </div>
                        ) : null}
                        {item.evidencePrompt ? (
                          <div className="evidence-prompt">
                            {item.evidencePrompt}
                          </div>
                        ) : null}
                        <div className="check-controls">
                          <div className="field">
                            <label htmlFor={`${item.id}-result`}>Result</label>
                            <select
                              id={`${item.id}-result`}
                              value={result?.result ?? "not_tested"}
                              onChange={(event) =>
                                onChecklistResultChange(item.id, {
                                  result: event.target.value as ChecklistResultValue,
                                  recordedAt: new Date().toISOString()
                                })
                              }
                            >
                              {checklistResultOptions.map((option) => (
                                <option key={option} value={option}>
                                  {formatValue(option)}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="field evidence-field">
                            <label htmlFor={`${item.id}-evidence`}>Evidence</label>
                            <textarea
                              id={`${item.id}-evidence`}
                              value={result?.evidence ?? ""}
                              onChange={(event) =>
                                onChecklistResultChange(item.id, {
                                  evidence: event.target.value,
                                  recordedAt: new Date().toISOString()
                                })
                              }
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {hiddenCheckCount > 0 ? (
                    <div className="show-more-checks">
                      <button
                        className="button-secondary"
                        type="button"
                        onClick={() => toggleExpandedCheckGroup(section.group)}
                      >
                        Show {hiddenCheckCount} more check(s)
                      </button>
                    </div>
                  ) : section.items.length > 3 ? (
                    <div className="show-more-checks">
                      <button
                        className="button-secondary"
                        type="button"
                        onClick={() => toggleExpandedCheckGroup(section.group)}
                      >
                        Show fewer checks
                      </button>
                    </div>
                  ) : null}
                </details>
                );
              })}
            </div>
            <div className="actions">
              <button
                type="button"
                className="button-primary"
                disabled={isUpdating}
                onClick={onUpdateDiagnosis}
              >
                {isUpdating ? "Updating..." : "Update Diagnosis"}
              </button>
            </div>
          </>
        )}

        {diagnosis ? (
          <div className="diagnosis-panel">
            <div className="diagnosis-hero">
              <div>
                <span className="section-kicker">Troubleshooting Summary</span>
                <h3>{diagnosis.currentLikelyCause.cause}</h3>
                <p>{diagnosis.currentLikelyCause.reasoning}</p>
              </div>
              <span className="confidence-pill">
                {formatValue(diagnosis.confidence)} confidence
              </span>
            </div>
            <div className="content-section">
              <h3>What to do next</h3>
              <ol className="list next-actions-list">
                {visibleNextActions.map((item, index) => (
                  <li key={`${item}-${index}`}>{item}</li>
                ))}
              </ol>
            </div>
            <EscalationBoundaryPanel diagnosis={diagnosis} />
          </div>
        ) : null}
      </div>
    </section>
  );
}
