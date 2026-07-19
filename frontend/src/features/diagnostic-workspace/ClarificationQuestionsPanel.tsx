import type { ClarificationAnswer, InitialTriageResponse } from "./types";

interface ClarificationQuestionsPanelProps {
  triage: InitialTriageResponse | null;
  answers: Record<string, ClarificationAnswer>;
  hasContinuedToChecks: boolean;
  onAnswerChange: (question: string, patch: Partial<ClarificationAnswer>) => void;
  onContinue: () => void;
}

type AnswerMode = "binary" | "scope" | "display_path" | "account_platform" | "text";

const optionSets: Record<Exclude<AnswerMode, "text">, string[]> = {
  binary: ["Yes", "No", "Not sure"],
  scope: ["Only me", "Multiple users", "Whole team", "Not sure"],
  display_path: [
    "Laptop screen",
    "External monitor",
    "Dock",
    "Projector",
    "Not sure"
  ],
  account_platform: [
    "Work account",
    "Personal account",
    "Microsoft 365",
    "VPN",
    "Other",
    "Not sure"
  ]
};

function answerModeForQuestion(question: string): AnswerMode {
  const normalized = question.toLowerCase();

  if (
    normalized.includes("exact") ||
    normalized.includes("error") ||
    normalized.includes("message") ||
    normalized.includes("symptom") ||
    normalized.startsWith("what ") ||
    normalized.startsWith("when ")
  ) {
    return "text";
  }

  if (
    normalized.includes("affected") ||
    normalized.includes("only you") ||
    normalized.includes("multiple users") ||
    normalized.includes("everyone") ||
    normalized.includes("many users")
  ) {
    return "scope";
  }

  if (
    normalized.includes("monitor") ||
    normalized.includes("display") ||
    normalized.includes("screen") ||
    normalized.includes("dock") ||
    normalized.includes("projector")
  ) {
    return "display_path";
  }

  if (
    normalized.includes("account") ||
    normalized.includes("login") ||
    normalized.includes("sign in") ||
    normalized.includes("sign-in") ||
    normalized.includes("password") ||
    normalized.includes("mfa") ||
    normalized.includes("vpn")
  ) {
    return "account_platform";
  }

  if (
    normalized.startsWith("did ") ||
    normalized.startsWith("do ") ||
    normalized.startsWith("does ") ||
    normalized.startsWith("is ") ||
    normalized.startsWith("are ") ||
    normalized.startsWith("can ") ||
    normalized.startsWith("has ") ||
    normalized.startsWith("have ") ||
    normalized.includes("whether")
  ) {
    return "binary";
  }

  return "text";
}

export function ClarificationQuestionsPanel({
  triage,
  answers,
  hasContinuedToChecks,
  onAnswerChange,
  onContinue
}: ClarificationQuestionsPanelProps) {
  if (!triage) {
    return null;
  }

  const visibleQuestions = triage.missingInformation.slice(0, 5);
  const unansweredCount = visibleQuestions.filter((item) => {
    const answer = answers[item.question];
    return !answer?.selectedOption.trim() && !answer?.details.trim();
  }).length;

  return (
    <section className="panel clarification-panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Questions to Narrow It Down</h2>
          <p className="panel-subtitle">
            Answer what you know. You can continue even if some details are unknown.
          </p>
        </div>
      </div>
      <div className="panel-body">
        {visibleQuestions.length === 0 ? (
          <div className="empty-state">
            No additional questions were identified. Continue to guided checks when
            ready.
          </div>
        ) : (
          <div className="clarification-list">
            {visibleQuestions.map((item, index) => {
            const answer = answers[item.question] ?? {
              question: item.question,
              selectedOption: "",
              details: ""
            };
            const mode = answerModeForQuestion(item.question);
            const options = mode === "text" ? [] : optionSets[mode];

              return (
                <div className="clarification-card" key={`${item.question}-${index}`}>
                  <div>
                    <h3>{item.question}</h3>
                    <p>{item.reason}</p>
                  </div>
                  {mode === "text" ? (
                    <div className="field">
                      <label htmlFor={`clarification-answer-${index}`}>Answer</label>
                      <textarea
                        id={`clarification-answer-${index}`}
                        value={answer.selectedOption}
                        onChange={(event) =>
                          onAnswerChange(item.question, {
                            question: item.question,
                            selectedOption: event.target.value
                          })
                        }
                      />
                    </div>
                  ) : (
                    <div className="option-grid">
                      {options.map((option) => (
                        <button
                          className={`option-button ${
                            answer.selectedOption === option ? "selected" : ""
                          }`}
                          key={option}
                          type="button"
                          onClick={() =>
                            onAnswerChange(item.question, {
                              question: item.question,
                              selectedOption: option
                            })
                          }
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="field">
                    <label htmlFor={`clarification-details-${index}`}>
                      Optional details
                    </label>
                    <textarea
                      id={`clarification-details-${index}`}
                      value={answer.details}
                      onChange={(event) =>
                        onAnswerChange(item.question, {
                          question: item.question,
                          details: event.target.value
                        })
                      }
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {hasContinuedToChecks && unansweredCount > 0 ? (
          <div className="soft-warning">
            Some information is still unknown. You can continue and update the
            diagnosis later.
          </div>
        ) : null}
        {!hasContinuedToChecks ? (
          <div className="actions">
            <button className="button-primary" type="button" onClick={onContinue}>
              Continue to Guided Checks
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
