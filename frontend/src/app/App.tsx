import { useMemo, useState } from "react";
import { analyzeTicket, updateDiagnosis } from "../features/diagnostic-workspace/api";
import type {
  ChecklistItem,
  ChecklistResult,
  ChecklistResultValue,
  InitialTriageResponse,
  MissingInformationItem,
  PossibleCause,
  TicketInput,
  UpdatedDiagnosisResponse
} from "../features/diagnostic-workspace/types";
import { emptyTicket } from "../features/diagnostic-workspace/types";

type AppStage =
  | "intake"
  | "analyzing"
  | "hypotheses"
  | "pinpoint"
  | "guided_checks"
  | "summary";

type QuestionAnswer = {
  choice: string;
  details: string;
};

type CheckOutcome = "pass" | "fail" | "not_checked";

type ActionCard = {
  action: string;
  why: string;
  expectedOutcome: string;
};

const examplePrompts = [
  "I can’t sign in to my work account",
  "My Wi-Fi keeps disconnecting",
  "My printer is online but nothing prints",
  "My monitor says no signal",
  "Outlook is not receiving emails",
  "Teams microphone is not working",
  "The VPN connection keeps failing",
  "I can’t access a shared folder"
];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong.";
}

function shortTitleFromIssue(userMessage: string): string {
  const trimmed = userMessage.trim();
  if (!trimmed) {
    return "Support issue";
  }

  return trimmed.length > 72 ? `${trimmed.slice(0, 69)}...` : trimmed;
}

function buildTicketPayload(issueText: string): TicketInput {
  const trimmedIssue = issueText.trim();
  return {
    ...emptyTicket,
    title: shortTitleFromIssue(trimmedIssue),
    userMessage: trimmedIssue,
    affectedService: "Unknown",
    deviceType: "Unknown",
    businessImpact: "Not provided yet"
  };
}

function formatValue(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function likelihoodLabel(cause: PossibleCause | undefined): string {
  if (!cause) {
    return "Needs confirmation";
  }

  return `${formatValue(cause.likelihood)} likelihood`;
}

function isOpenQuestion(question: string): boolean {
  const normalized = question.toLowerCase();
  return (
    normalized.startsWith("what ") ||
    normalized.startsWith("which ") ||
    normalized.startsWith("when ") ||
    normalized.startsWith("where ") ||
    normalized.startsWith("how ") ||
    normalized.includes("exact") ||
    normalized.includes("error message") ||
    normalized.includes("path") ||
    normalized.includes("name")
  );
}

function inferEitherOrOptions(question: string): string[] | null {
  const normalized = question.toLowerCase();

  if (!normalized.includes(" or ")) {
    return null;
  }
  if (normalized.includes("one user") || normalized.includes("multiple users")) {
    return ["One user", "Multiple users", "Not sure"];
  }
  if (normalized.includes("only you") || normalized.includes("other users")) {
    return ["Only me", "Other users", "Not sure"];
  }
  if (normalized.includes("desktop") && normalized.includes("browser")) {
    return ["Desktop app", "Browser", "Not sure"];
  }
  if (normalized.includes("one document") || normalized.includes("all print jobs")) {
    return ["One document/app", "All print jobs", "Not sure"];
  }
  if (normalized.includes("only this action") || normalized.includes("other features")) {
    return ["Only this action", "Other features also fail", "Not sure"];
  }

  return null;
}

function buildAnswerSummary(
  questions: MissingInformationItem[],
  answers: Record<string, QuestionAnswer>
): string[] {
  return questions
    .map((item) => {
      const answer = answers[item.question];
      if (!answer || (!answer.choice.trim() && !answer.details.trim())) {
        return null;
      }

      const response = [answer.choice, answer.details]
        .filter((part) => part.trim())
        .join(" - ");
      return `${item.question}: ${response}`;
    })
    .filter((item): item is string => Boolean(item));
}

function checklistResultForClarificationAnswer(
  answer: QuestionAnswer
): ChecklistResultValue {
  const response = [answer.choice, answer.details].join(" ").trim().toLowerCase();
  if (!response) {
    return "not_tested";
  }
  if (response.includes("not sure")) {
    return "user_unsure";
  }
  if (response === "yes") {
    return "yes";
  }
  if (response === "no") {
    return "no";
  }
  return "works";
}

function clarificationResultsFromAnswers(
  questions: MissingInformationItem[],
  answers: Record<string, QuestionAnswer>
): ChecklistResult[] {
  return questions
    .map((item, index) => {
      const answer = answers[item.question];
      if (!answer || (!answer.choice.trim() && !answer.details.trim())) {
        return null;
      }

      const response = [answer.choice, answer.details]
        .filter((part) => part.trim())
        .join(" - ");
      return {
        stepId: `clarification-${index + 1}`,
        result: checklistResultForClarificationAnswer(answer),
        evidence: `Clarification answer. Question: ${item.question} Answer: ${response}`,
        recordedAt: new Date().toISOString()
      };
    })
    .filter((item): item is ChecklistResult => Boolean(item));
}

function stageIndex(stage: AppStage): number {
  switch (stage) {
    case "intake":
      return 0;
    case "analyzing":
      return 1;
    case "hypotheses":
      return 2;
    case "pinpoint":
      return 3;
    case "guided_checks":
      return 4;
    case "summary":
      return 5;
  }
}

function cleanSummaryText(summary: string, ticket: TicketInput | null): string {
  const reportedIssue = ticket?.userMessage.trim();
  if (reportedIssue) {
    return reportedIssue;
  }

  return summary
    .replace(/Affected service:\s*Unknown\.?/gi, "")
    .replace(/Environment context:[^.]+\.?/gi, "")
    .replace(/User reports:\s*/gi, "")
    .replace(/\s+/g, " ")
    .trim();
}

function conciseText(value: string, maxLength = 118): string {
  const compact = value.replace(/\s+/g, " ").trim();
  if (compact.length <= maxLength) {
    return compact;
  }

  return `${compact.slice(0, maxLength - 3).trim()}...`;
}

function checklistResultForOutcome(
  item: ChecklistItem,
  outcome: CheckOutcome
): ChecklistResultValue {
  if (outcome === "not_checked") {
    return "not_tested";
  }
  if (item.expectedResultType === "yes_no") {
    return outcome === "pass" ? "yes" : "no";
  }
  if (item.expectedResultType === "text") {
    return outcome === "pass" ? "works" : "user_unsure";
  }
  if (item.expectedResultType === "not_applicable") {
    return "not_tested";
  }
  return outcome === "pass" ? "works" : "does_not_work";
}

function outcomeFromResult(result: ChecklistResult | undefined): CheckOutcome {
  if (!result || result.result === "not_tested") {
    return "not_checked";
  }
  if (["works", "yes"].includes(result.result)) {
    return "pass";
  }
  return "fail";
}

function visibleChecks(triage: InitialTriageResponse): ChecklistItem[] {
  const safeChecks = triage.checklist.filter(
    (item) => item.group !== "escalation_admin_infrastructure"
  );
  return (safeChecks.length > 0 ? safeChecks : triage.checklist).slice(0, 5);
}

function buildCheckSummary(
  checks: ChecklistItem[],
  checklistResults: Record<string, ChecklistResult>
): string[] {
  return checks
    .map((item) => {
      const result = checklistResults[item.id];
      if (!result || result.result === "not_tested") {
        return null;
      }

      const resultLabel =
        outcomeFromResult(result) === "pass" ? "Confirmed" : "Not confirmed";
      const evidence = result.evidence.trim()
        ? ` Evidence: ${result.evidence.trim()}`
        : "";
      return `${item.step}: ${resultLabel}.${evidence}`;
    })
    .filter((item): item is string => Boolean(item));
}

function actionCardsFromDiagnosis(
  diagnosis: UpdatedDiagnosisResponse | null,
  checks: ChecklistItem[]
): ActionCard[] {
  const diagnosisActions = diagnosis
    ? diagnosis.nextBestActions && diagnosis.nextBestActions.length > 0
      ? diagnosis.nextBestActions
      : [diagnosis.nextBestAction]
    : [];

  const cards = diagnosisActions
    .filter(Boolean)
    .slice(0, 3)
    .map((action) => ({
      action: conciseText(action, 96),
      why: "This is the next evidence-based step from the updated diagnosis.",
      expectedOutcome: "Confirm whether the current likely direction still fits."
    }));

  if (cards.length > 0) {
    return cards;
  }

  return checks.slice(0, 3).map((item) => ({
    action: conciseText(item.step, 96),
    why: conciseText(item.evidencePrompt || item.why, 110),
    expectedOutcome: "Collect evidence that helps confirm or rule out this path."
  }));
}

function StageProgress({ stage }: { stage: AppStage }) {
  const currentIndex = stageIndex(stage);
  const labels = [
    "Describe",
    "Analyze",
    "Hypotheses",
    "Pinpoint",
    "Checks",
    "Summary"
  ];

  return (
    <div className="stage-progress" aria-label="Diagnosis progress">
      {labels.map((label, index) => (
        <span
          className={`stage-dot ${index <= currentIndex ? "stage-dot-active" : ""}`}
          key={label}
          title={label}
        />
      ))}
    </div>
  );
}

function AppHeader({ onNewDiagnosis }: { onNewDiagnosis: () => void }) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-mark">AI</span>
        <span>SupportFlow AI</span>
      </div>
      <button className="ghost-button" type="button" onClick={onNewDiagnosis}>
        New Diagnosis
      </button>
    </header>
  );
}

function IntakeStage({
  issueText,
  error,
  onIssueTextChange,
  onStart
}: {
  issueText: string;
  error: string | null;
  onIssueTextChange: (value: string) => void;
  onStart: () => void;
}) {
  return (
    <section className="stage-card intake-stage">
      <p className="stage-kicker">Step 1 - Describe</p>
      <h1>What's the problem?</h1>
      <p className="stage-subtitle">
        Describe the issue you're having, and we'll help you work through it.
      </p>
      {error ? <div className="error-banner">{error}</div> : null}
      <textarea
        className="issue-textarea"
        value={issueText}
        onChange={(event) => onIssueTextChange(event.target.value)}
        placeholder="e.g. I cannot access the shared folder and it says access denied."
      />
      <button
        className="primary-action"
        disabled={!issueText.trim()}
        type="button"
        onClick={onStart}
      >
        Start Diagnosis -&gt;
      </button>
      <div className="example-area">
        <span>Try an example</span>
        <div className="example-chip-grid">
          {examplePrompts.map((example) => (
            <button
              className="example-chip"
              key={example}
              type="button"
              onClick={() => onIssueTextChange(example)}
            >
              {example}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function AnalyzingStage() {
  return (
    <section className="stage-card">
      <p className="stage-kicker">Step 2 - Analyze</p>
      <h1>Analyzing your issue...</h1>
      <p className="stage-subtitle">
        AI is narrowing down the most likely troubleshooting path.
      </p>
      <div className="skeleton-grid" aria-label="Loading analysis">
        {Array.from({ length: 6 }).map((_, index) => (
          <div className="skeleton-card" key={index}>
            <span className="skeleton-icon" />
            <span className="skeleton-pill" />
            <span className="skeleton-line skeleton-line-strong" />
            <span className="skeleton-line" />
          </div>
        ))}
      </div>
    </section>
  );
}

function HypothesesStage({
  triage,
  unlikelyCauseIds,
  onToggleUnlikely,
  onContinue
}: {
  triage: InitialTriageResponse;
  unlikelyCauseIds: Set<string>;
  onToggleUnlikely: (causeId: string) => void;
  onContinue: () => void;
}) {
  const causes = triage.possibleCauses.slice(0, 6);

  return (
    <section className="stage-card">
      <p className="stage-kicker">Step 3 - Narrow</p>
      <h1>Initial Hypotheses</h1>
      <p className="stage-subtitle">
        These are starting points, not confirmed causes.
      </p>
      <div className="context-strip">
        <span>{formatValue(triage.classification.category)}</span>
        <span>{cleanSummaryText(triage.summary, null)}</span>
      </div>
      <div className="hypothesis-grid">
        {causes.map((cause, index) => {
          const causeId = `${cause.cause}-${index}`;
          const isUnlikely = unlikelyCauseIds.has(causeId);
          return (
            <button
              className={`hypothesis-card ${isUnlikely ? "hypothesis-card-muted" : ""}`}
              key={causeId}
              type="button"
              onClick={() => onToggleUnlikely(causeId)}
            >
              <div className="card-topline">
                <span className="mini-number">{index + 1}</span>
                <span className={`likelihood likelihood-${cause.likelihood}`}>
                  {formatValue(cause.likelihood)}
                </span>
              </div>
              <h2>{cause.cause}</h2>
              <p>{cause.reason}</p>
              <span className="card-action">
                {isUnlikely ? "Marked unlikely" : "Mark as unlikely"}
              </span>
            </button>
          );
        })}
      </div>
      <button className="primary-action" type="button" onClick={onContinue}>
        Continue to Questions -&gt;
      </button>
    </section>
  );
}

function QuestionsStage({
  triage,
  answers,
  onAnswerChange,
  onContinue
}: {
  triage: InitialTriageResponse;
  answers: Record<string, QuestionAnswer>;
  onAnswerChange: (question: string, patch: Partial<QuestionAnswer>) => void;
  onContinue: () => void;
}) {
  const questions = triage.missingInformation.slice(0, 5);

  return (
    <section className="stage-card">
      <p className="stage-kicker">Step 4 - Pinpoint</p>
      <h1>Answer to pinpoint</h1>
      <p className="stage-subtitle">
        These questions help narrow down the most likely cause.
      </p>
      <div className="question-stack">
        {questions.length > 0 ? (
          questions.map((item, index) => {
            const answer = answers[item.question] ?? { choice: "", details: "" };
            const openQuestion = isOpenQuestion(item.question);
            const eitherOrOptions = openQuestion
              ? null
              : inferEitherOrOptions(item.question);
            const options = eitherOrOptions ?? ["Yes", "No", "Not sure"];

            return (
              <article className="question-card" key={`${item.question}-${index}`}>
                <div className="question-heading">
                  <span className="mini-number">{index + 1}</span>
                  <h2>{item.question}</h2>
                </div>
                <p>
                  <strong>Why this matters:</strong> {item.reason}
                </p>
                {openQuestion ? (
                  <div className="open-answer">
                    <input
                      value={answer.details}
                      onChange={(event) =>
                        onAnswerChange(item.question, {
                          details: event.target.value,
                          choice: ""
                        })
                      }
                      placeholder="Type what you know..."
                    />
                    <button
                      className={answer.choice === "Not sure" ? "answer-selected" : ""}
                      type="button"
                      onClick={() =>
                        onAnswerChange(item.question, {
                          choice: "Not sure",
                          details: ""
                        })
                      }
                    >
                      Not sure
                    </button>
                  </div>
                ) : (
                  <div className="answer-options">
                    {options.map((option) => (
                      <button
                        className={answer.choice === option ? "answer-selected" : ""}
                        key={option}
                        type="button"
                        onClick={() =>
                          onAnswerChange(item.question, {
                            choice: option,
                            details: ""
                          })
                        }
                      >
                        {option}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            );
          })
        ) : (
          <div className="empty-card">
            No extra questions were returned. Continue with the available issue
            details.
          </div>
        )}
      </div>
      <button className="primary-action" type="button" onClick={onContinue}>
        Continue to Guided Checks -&gt;
      </button>
    </section>
  );
}

function GuidedChecksStage({
  triage,
  checklistResults,
  currentCheckIndex,
  isUpdatingDiagnosis,
  updateWarning,
  onChecklistResultChange,
  onContinueCheck,
  onUpdateDiagnosis
}: {
  triage: InitialTriageResponse;
  checklistResults: Record<string, ChecklistResult>;
  currentCheckIndex: number;
  isUpdatingDiagnosis: boolean;
  updateWarning: string | null;
  onChecklistResultChange: (
    item: ChecklistItem,
    patch: Partial<ChecklistResult>
  ) => void;
  onContinueCheck: () => void;
  onUpdateDiagnosis: () => void;
}) {
  const checks = visibleChecks(triage);
  const safeIndex = Math.min(currentCheckIndex, Math.max(checks.length - 1, 0));
  const item = checks[safeIndex];
  const isFinalCheck = safeIndex >= checks.length - 1;

  if (!item) {
    return (
      <section className="stage-card">
        <p className="stage-kicker">Step 5 - Checks</p>
        <h1>Guided Checks</h1>
        <p className="stage-subtitle">
          No checklist items were returned. Continue to the summary with the
          information collected so far.
        </p>
        <button
          className="primary-action"
          disabled={isUpdatingDiagnosis}
          type="button"
          onClick={onUpdateDiagnosis}
        >
          Generate Summary -&gt;
        </button>
      </section>
    );
  }

  const result = checklistResults[item.id];
  const outcome = outcomeFromResult(result);

  return (
    <section className="stage-card">
      <p className="stage-kicker">Step 5 - Checks</p>
      <h1>Guided Checks</h1>
      <p className="stage-subtitle">
        Run these Level 1 checks before deciding the next step.
      </p>
      {updateWarning ? <div className="warning-banner">{updateWarning}</div> : null}
      <div className="guided-check-progress">
        Check {safeIndex + 1} of {checks.length}
      </div>
      <article className="check-card check-card-single" key={item.id}>
        <div className="question-heading">
          <span className="mini-number">{safeIndex + 1}</span>
          <h2>{item.step}</h2>
        </div>
        <p>{item.evidencePrompt || item.why}</p>
        <div className="check-options">
          {[
            ["pass", "Confirmed"],
            ["fail", "Not confirmed"],
            ["not_checked", "Not sure"]
          ].map(([value, label]) => (
            <button
              className={outcome === value ? "answer-selected" : ""}
              key={value}
              type="button"
              onClick={() =>
                onChecklistResultChange(item, {
                  result: checklistResultForOutcome(item, value as CheckOutcome),
                  recordedAt: new Date().toISOString()
                })
              }
            >
              {label}
            </button>
          ))}
        </div>
        <textarea
          className="evidence-input"
          value={result?.evidence ?? ""}
          onChange={(event) =>
            onChecklistResultChange(item, {
              evidence: event.target.value,
              recordedAt: new Date().toISOString()
            })
          }
          placeholder="Add evidence or observation..."
        />
      </article>
      <button
        className="primary-action"
        disabled={isUpdatingDiagnosis}
        type="button"
        onClick={isFinalCheck ? onUpdateDiagnosis : onContinueCheck}
      >
        {isUpdatingDiagnosis
          ? "Updating Diagnosis..."
          : isFinalCheck
            ? "Generate Summary ->"
            : "Continue Check ->"}
      </button>
    </section>
  );
}

function SummaryStage({
  triage,
  ticket,
  answers,
  checklistResults,
  diagnosis,
  unlikelyCauseIds,
  isTicketNoteOpen,
  onToggleTicketNote,
  onCopy,
  onNewDiagnosis
}: {
  triage: InitialTriageResponse;
  ticket: TicketInput | null;
  answers: Record<string, QuestionAnswer>;
  checklistResults: Record<string, ChecklistResult>;
  diagnosis: UpdatedDiagnosisResponse | null;
  unlikelyCauseIds: Set<string>;
  isTicketNoteOpen: boolean;
  onToggleTicketNote: () => void;
  onCopy: () => void;
  onNewDiagnosis: () => void;
}) {
  const checks = visibleChecks(triage);
  const likelyCause =
    diagnosis?.currentLikelyCause.cause ||
    triage.possibleCauses.find(
      (cause, index) => !unlikelyCauseIds.has(`${cause.cause}-${index}`)
    )?.cause ||
    "Needs more information";
  const confidence =
    diagnosis?.currentLikelyCause.confidence ||
    triage.possibleCauses.find(
      (cause, index) => !unlikelyCauseIds.has(`${cause.cause}-${index}`)
    )?.likelihood;
  const answerSummary = buildAnswerSummary(triage.missingInformation, answers);
  const checkSummary = buildCheckSummary(checks, checklistResults);
  const whyBullets = [
    `Reported issue: ${cleanSummaryText(triage.summary, ticket)}`,
    answerSummary.length > 0
      ? `${answerSummary.length} clarification answer(s) helped narrow the symptom.`
      : "Clarification answers are still limited, so keep the conclusion tentative.",
    checkSummary.length > 0
      ? `${checkSummary.length} guided check result(s) were recorded before the summary.`
      : "Guided checks were not fully recorded yet.",
    diagnosis?.currentLikelyCause.reasoning
      ? conciseText(diagnosis.currentLikelyCause.reasoning, 130)
      : ""
  ].filter(Boolean).slice(0, 3);
  const actionCards = actionCardsFromDiagnosis(diagnosis, checks).slice(0, 3);

  return (
    <section className="stage-card summary-stage">
      <p className="stage-kicker">Step 6 - Summary</p>
      <h1>Troubleshooting Summary</h1>
      <p className="stage-subtitle">
        Working hypothesis based on the information collected so far.
      </p>

      <article className="summary-cause-card">
        <div>
          <span className="summary-label">Current Likely Direction</span>
          <h2>{likelyCause}</h2>
        </div>
        <span className="confidence-pill">
          {confidence ? `${formatValue(confidence)} confidence` : "Needs evidence"}
        </span>
        <p>Working hypothesis based on the information collected so far.</p>
      </article>

      <article className="summary-section-card">
        <h2>Why this seems likely</h2>
        <ul className="bullet-list">
          {whyBullets.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      </article>

      <article className="summary-section-card">
        <h2>Recommended next steps</h2>
        <div className="action-card-list">
          {actionCards.map((item, index) => (
            <div className="action-card" key={`${item.action}-${index}`}>
              <span className="mini-number">{index + 1}</span>
              <div>
                <h3>{item.action}</h3>
                <p>
                  <strong>Why:</strong> {item.why}
                </p>
                <p>
                  <strong>Expected outcome:</strong> {item.expectedOutcome}
                </p>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="summary-section-card ticket-note-preview">
        <div className="ticket-note-heading">
          <h2>Ticket note</h2>
          <button className="ghost-button" type="button" onClick={onToggleTicketNote}>
            {isTicketNoteOpen ? "Hide preview" : "Preview ticket note"}
          </button>
        </div>
        {isTicketNoteOpen ? (
          <pre>{buildTicketNote({
            triage,
            ticket,
            answers,
            checklistResults,
            diagnosis,
            unlikelyCauseIds
          })}</pre>
        ) : (
          <p className="ticket-note-collapsed">
            A compact ticket note is ready to copy when you need it.
          </p>
        )}
      </article>

      <div className="summary-actions">
        <button className="secondary-action" type="button" onClick={onCopy}>
          Copy Ticket Note
        </button>
        <button className="primary-action" type="button" onClick={onNewDiagnosis}>
          New Diagnosis
        </button>
      </div>
    </section>
  );
}

function buildTicketNote({
  triage,
  ticket,
  answers,
  checklistResults,
  diagnosis,
  unlikelyCauseIds
}: {
  triage: InitialTriageResponse;
  ticket: TicketInput | null;
  answers: Record<string, QuestionAnswer>;
  checklistResults: Record<string, ChecklistResult>;
  diagnosis: UpdatedDiagnosisResponse | null;
  unlikelyCauseIds: Set<string>;
}): string {
  const checks = visibleChecks(triage);
  const likelyCause =
    diagnosis?.currentLikelyCause.cause ||
    triage.possibleCauses.find(
      (cause, index) => !unlikelyCauseIds.has(`${cause.cause}-${index}`)
    )?.cause ||
    "Needs more information";
  const answerSummary = buildAnswerSummary(triage.missingInformation, answers);
  const checkSummary = buildCheckSummary(checks, checklistResults);
  const nextSteps = actionCardsFromDiagnosis(diagnosis, checks)
    .slice(0, 5)
    .map((item) => `- ${item.action}`);

  return [
    "SupportFlow AI ticket note",
    `Issue: ${ticket?.userMessage || cleanSummaryText(triage.summary, ticket)}`,
    `Category: ${formatValue(triage.classification.category)}`,
    `Current likely direction: ${likelyCause}`,
    "",
    "Answers collected:",
    answerSummary.length > 0
      ? answerSummary.slice(0, 5).map((item) => `- ${item}`).join("\n")
      : "- Not provided yet",
    "",
    "Checks completed:",
    checkSummary.length > 0
      ? checkSummary.slice(0, 5).map((item) => `- ${item}`).join("\n")
      : "- No recorded guided check results yet",
    "",
    "Recommended next steps:",
    nextSteps.length > 0 ? nextSteps.join("\n") : "- Continue collecting Level 1 evidence."
  ].join("\n");
}

export function App() {
  const [stage, setStage] = useState<AppStage>("intake");
  const [issueText, setIssueText] = useState("");
  const [ticket, setTicket] = useState<TicketInput | null>(null);
  const [triage, setTriage] = useState<InitialTriageResponse | null>(null);
  const [diagnosis, setDiagnosis] = useState<UpdatedDiagnosisResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, QuestionAnswer>>({});
  const [checklistResults, setChecklistResults] = useState<
    Record<string, ChecklistResult>
  >({});
  const [currentCheckIndex, setCurrentCheckIndex] = useState(0);
  const [unlikelyCauseIds, setUnlikelyCauseIds] = useState<Set<string>>(
    () => new Set()
  );
  const [isTicketNoteOpen, setIsTicketNoteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updateWarning, setUpdateWarning] = useState<string | null>(null);
  const [isUpdatingDiagnosis, setIsUpdatingDiagnosis] = useState(false);
  const [copyStatus, setCopyStatus] = useState<string | null>(null);

  const resetForNewDiagnosis = () => {
    setStage("intake");
    setIssueText("");
    setTicket(null);
    setTriage(null);
    setDiagnosis(null);
    setAnswers({});
    setChecklistResults({});
    setCurrentCheckIndex(0);
    setUnlikelyCauseIds(new Set());
    setIsTicketNoteOpen(false);
    setError(null);
    setUpdateWarning(null);
    setIsUpdatingDiagnosis(false);
    setCopyStatus(null);
  };

  const handleStartDiagnosis = async () => {
    const trimmedIssue = issueText.trim();
    if (!trimmedIssue) {
      return;
    }

    const nextTicket = buildTicketPayload(trimmedIssue);
    setStage("analyzing");
    setTicket(nextTicket);
    setTriage(null);
    setDiagnosis(null);
    setAnswers({});
    setChecklistResults({});
    setCurrentCheckIndex(0);
    setUnlikelyCauseIds(new Set());
    setIsTicketNoteOpen(false);
    setError(null);
    setUpdateWarning(null);
    setCopyStatus(null);

    try {
      const response = await analyzeTicket(nextTicket);
      setTriage(response);
      setStage("hypotheses");
    } catch (requestError) {
      setError(errorMessage(requestError));
      setStage("intake");
    }
  };

  const handleToggleUnlikely = (causeId: string) => {
    setUnlikelyCauseIds((current) => {
      const next = new Set(current);
      if (next.has(causeId)) {
        next.delete(causeId);
      } else {
        next.add(causeId);
      }
      return next;
    });
  };

  const handleAnswerChange = (
    question: string,
    patch: Partial<QuestionAnswer>
  ) => {
    setAnswers((current) => ({
      ...current,
      [question]: {
        choice: current[question]?.choice ?? "",
        details: current[question]?.details ?? "",
        ...patch
      }
    }));
  };

  const handleChecklistResultChange = (
    item: ChecklistItem,
    patch: Partial<ChecklistResult>
  ) => {
    setChecklistResults((current) => {
      const existing = current[item.id];
      const nextResult: ChecklistResult = {
        stepId: item.id,
        result: existing?.result ?? "not_tested",
        evidence: existing?.evidence ?? "",
        recordedAt: existing?.recordedAt ?? new Date().toISOString(),
        ...patch
      };
      return {
        ...current,
        [item.id]: nextResult
      };
    });
  };

  const handleContinueCheck = () => {
    if (!triage) {
      return;
    }

    const checks = visibleChecks(triage);
    setCurrentCheckIndex((current) =>
      Math.min(current + 1, Math.max(checks.length - 1, 0))
    );
  };

  const handleUpdateDiagnosis = async () => {
    if (!ticket || !triage) {
      setStage("summary");
      return;
    }

    setIsUpdatingDiagnosis(true);
    setUpdateWarning(null);
    try {
      const results = [
        ...clarificationResultsFromAnswers(triage.missingInformation, answers),
        ...Object.values(checklistResults)
      ];
      const response = await updateDiagnosis(ticket, results);
      setDiagnosis(response);
    } catch (requestError) {
      setUpdateWarning(
        `Diagnosis update was unavailable. Summary uses triage and collected evidence. ${errorMessage(requestError)}`
      );
    } finally {
      setIsUpdatingDiagnosis(false);
      setStage("summary");
    }
  };

  const ticketNote = useMemo(() => {
    if (!triage) {
      return "";
    }

    return buildTicketNote({
      triage,
      ticket,
      answers,
      checklistResults,
      diagnosis,
      unlikelyCauseIds
    });
  }, [answers, checklistResults, diagnosis, ticket, triage, unlikelyCauseIds]);

  const handleCopyTicketNote = async () => {
    if (!ticketNote) {
      return;
    }

    try {
      await navigator.clipboard.writeText(ticketNote);
      setCopyStatus("Ticket note copied.");
    } catch {
      setCopyStatus("Copy failed. Select the note text manually.");
    }
  };

  return (
    <main className="app-shell">
      <AppHeader onNewDiagnosis={resetForNewDiagnosis} />
      <div className="center-flow">
        <StageProgress stage={stage} />
        {stage === "intake" ? (
          <IntakeStage
            issueText={issueText}
            error={error}
            onIssueTextChange={(value) => {
              setIssueText(value);
              setError(null);
              setCopyStatus(null);
            }}
            onStart={handleStartDiagnosis}
          />
        ) : null}
        {stage === "analyzing" ? <AnalyzingStage /> : null}
        {stage === "hypotheses" && triage ? (
          <HypothesesStage
            triage={triage}
            unlikelyCauseIds={unlikelyCauseIds}
            onToggleUnlikely={handleToggleUnlikely}
            onContinue={() => setStage("pinpoint")}
          />
        ) : null}
        {stage === "pinpoint" && triage ? (
          <QuestionsStage
            triage={triage}
            answers={answers}
            onAnswerChange={handleAnswerChange}
            onContinue={() => {
              setCurrentCheckIndex(0);
              setStage("guided_checks");
            }}
          />
        ) : null}
        {stage === "guided_checks" && triage ? (
          <GuidedChecksStage
            triage={triage}
            checklistResults={checklistResults}
            currentCheckIndex={currentCheckIndex}
            isUpdatingDiagnosis={isUpdatingDiagnosis}
            updateWarning={updateWarning}
            onChecklistResultChange={handleChecklistResultChange}
            onContinueCheck={handleContinueCheck}
            onUpdateDiagnosis={handleUpdateDiagnosis}
          />
        ) : null}
        {stage === "summary" && triage ? (
          <>
            {updateWarning ? <div className="warning-banner">{updateWarning}</div> : null}
            <SummaryStage
              triage={triage}
              ticket={ticket}
              answers={answers}
              checklistResults={checklistResults}
              diagnosis={diagnosis}
              unlikelyCauseIds={unlikelyCauseIds}
              isTicketNoteOpen={isTicketNoteOpen}
              onToggleTicketNote={() => setIsTicketNoteOpen((current) => !current)}
              onCopy={handleCopyTicketNote}
              onNewDiagnosis={resetForNewDiagnosis}
            />
            {copyStatus ? <div className="copy-status">{copyStatus}</div> : null}
          </>
        ) : null}
      </div>
    </main>
  );
}
